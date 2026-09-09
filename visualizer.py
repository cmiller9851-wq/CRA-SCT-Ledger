import ui
import math
import random
import time
from objc_util import on_main_thread

# Queue configuration
BUFFER_SIZE = 8
BUFFER_MASK = BUFFER_SIZE - 1

class Slot:
    def __init__(self, index):
        self.phase_stamp = index
        self.payload = None

class QueueState:
    def __init__(self):
        self.head_index = 0
        self.tail_index = 0
        self.slots = [Slot(i) for i in range(BUFFER_SIZE)]

class VirtualThread:
    def __init__(self, tid, is_producer):
        self.tid = tid
        self.is_producer = is_producer
        self.color = '#ff6b6b' if is_producer else '#4dadf7'
        self.reset()
        
    def reset(self):
        self.state = "IDLE"  # IDLE, CLAIMING, WRITING, RELEASING, POLLING, READING, FREEING
        self.target_index = None
        self.temp_head = None
        self.temp_tail = None
        self.payload_to_write = None
        self.payload_read = None
        
    @property
    def name(self):
        prefix = "Producer" if self.is_producer else "Consumer"
        return f"{prefix} {self.tid}"

class QueueVisualizer(ui.View):
    def __init__(self):
        self.background_color = '#121214'
        self.queue = QueueState()
        
        self.threads = [
            VirtualThread(1, is_producer=True),
            VirtualThread(2, is_producer=True),
            VirtualThread(1, is_producer=False),
            VirtualThread(2, is_producer=False)
        ]
        
        self.active_thread_index = 0
        self.log_messages = ["[*] Visualizer initialized. Tap 'Step' or 'Auto-Play'."]
        self.is_playing = False
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header text
        self.title_label = ui.Label(frame=(20, 20, 400, 30))
        self.title_label.text = "Lock-Free MPMC Queue Simulator"
        self.title_label.text_color = '#ffffff'
        self.title_label.font = ('HelveticaNeue-Bold', 20)
        self.add_subview(self.title_label)
        
        self.subtitle = ui.Label(frame=(20, 50, 500, 20))
        self.subtitle.text = "Visualizing C11 Atomic CAS & Release-Acquire Semantics"
        self.subtitle.text_color = '#8e8e93'
        self.subtitle.font = ('HelveticaNeue', 12)
        self.add_subview(self.subtitle)
        
        # Interactivity controls
        self.step_btn = ui.Button(frame=(20, 80, 100, 40))
        self.step_btn.title = "Step Cycle"
        self.step_btn.background_color = '#2c2c2e'
        self.step_btn.tint_color = '#34c759'
        self.step_btn.corner_radius = 6
        self.step_btn.action = self.step_clicked
        self.add_subview(self.step_btn)
        
        self.play_btn = ui.Button(frame=(130, 80, 100, 40))
        self.play_btn.title = "Auto-Play"
        self.play_btn.background_color = '#2c2c2e'
        self.play_btn.tint_color = '#ff9500'
        self.play_btn.corner_radius = 6
        self.play_btn.action = self.toggle_play
        self.add_subview(self.play_btn)
        
        self.reset_btn = ui.Button(frame=(240, 80, 100, 40))
        self.reset_btn.title = "Reset"
        self.reset_btn.background_color = '#2c2c2e'
        self.reset_btn.tint_color = '#ff3b30'
        self.reset_btn.corner_radius = 6
        self.reset_btn.action = self.reset_sim
        self.add_subview(self.reset_btn)
        
        # Ring canvas
        self.canvas = ui.View(frame=(20, 140, 360, 360))
        self.canvas.draw = self.draw_canvas
        self.add_subview(self.canvas)
        
        # Live log monitor
        self.log_box = ui.TextView(frame=(400, 140, 340, 360))
        self.log_box.background_color = '#1c1c1e'
        self.log_box.text_color = '#34c759'
        self.log_box.font = ('CourierNewPSMT', 11)
        self.log_box.editable = False
        self.log_box.text = "\n".join(self.log_messages)
        self.add_subview(self.log_box)
        
        # Statistics
        self.stats_panel = ui.View(frame=(400, 20, 340, 110))
        self.stats_panel.background_color = '#1c1c1e'
        self.stats_panel.corner_radius = 8
        self.add_subview(self.stats_panel)
        
        self.head_lbl = ui.Label(frame=(15, 10, 150, 20))
        self.head_lbl.text_color = '#ff6b6b'
        self.head_lbl.font = ('HelveticaNeue-Bold', 14)
        self.stats_panel.add_subview(self.head_lbl)
        
        self.tail_lbl = ui.Label(frame=(15, 35, 150, 20))
        self.tail_lbl.text_color = '#4dadf7'
        self.tail_lbl.font = ('HelveticaNeue-Bold', 14)
        self.stats_panel.add_subview(self.tail_lbl)
        
        self.thread_lbl = ui.Label(frame=(15, 65, 310, 40))
        self.thread_lbl.text_color = '#ffffff'
        self.thread_lbl.font = ('HelveticaNeue', 12)
        self.thread_lbl.number_of_lines = 2
        self.stats_panel.add_subview(self.thread_lbl)
        
        self.update_labels()
        
    def add_log(self, text):
        self.log_messages.append(text)
        if len(self.log_messages) > 50:
            self.log_messages.pop(0)
        self.log_box.text = "\n".join(self.log_messages)
        self.log_box.selected_range = (len(self.log_box.text), len(self.log_box.text))
        
    def update_labels(self):
        self.head_lbl.text = f"head_index: {self.queue.head_index}"
        self.tail_lbl.text = f"tail_index: {self.queue.tail_index}"
        active = self.threads[self.active_thread_index]
        self.thread_lbl.text = f"Scheduler Focus: {active.name}\nState: {active.state}"
        
    def reset_sim(self, sender):
        self.queue = QueueState()
        for t in self.threads:
            t.reset()
        self.active_thread_index = 0
        self.log_messages = ["[*] Simulation State Reset."]
        self.log_box.text = self.log_messages[0]
        self.update_labels()
        self.canvas.set_needs_display()
        
    def step_clicked(self, sender):
        self.run_one_step()
        
    def toggle_play(self, sender):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_btn.title = "Pause"
            self.play_btn.tint_color = '#ff3b30'
            self.auto_step_loop()
        else:
            self.play_btn.title = "Auto-Play"
            self.play_btn.tint_color = '#ff9500'
            
    def auto_step_loop(self):
        if self.is_playing:
            self.run_one_step()
            ui.delay(self.auto_step_loop, 0.4)
            
    def run_one_step(self):
        thread = self.threads[self.active_thread_index]
        self.execute_thread_instruction(thread)
        self.active_thread_index = random.randint(0, len(self.threads) - 1)
        self.update_labels()
        self.canvas.set_needs_display()
        
    def execute_thread_instruction(self, t):
        q = self.queue
        
        if t.is_producer:
            if t.state == "IDLE":
                t.temp_head = q.head_index
                t.state = "CLAIMING"
                self.add_log(f"[{t.name}] Loading head_index ({t.temp_head}) to initiate CAS write.")
                
            elif t.state == "CLAIMING":
                if (t.temp_head - q.tail_index) >= BUFFER_SIZE:
                    self.add_log(f"[{t.name}] Queue is FULL. Producer spinning...")
                    t.state = "IDLE"
                    return
                
                slot_idx = t.temp_head & BUFFER_MASK
                if q.head_index == t.temp_head:
                    q.head_index += 1
                    t.target_index = slot_idx
                    t.payload_to_write = f"D-{random.randint(10,99)}"
                    t.state = "WRITING"
                    self.add_log(f"[{t.name}] CAS Success! Claimed slot {slot_idx} for sequence {t.temp_head}.")
                else:
                    self.add_log(f"[{t.name}] CAS Failed! head_index updated by competitor. Retrying...")
                    t.state = "IDLE"
                    
            elif t.state == "WRITING":
                slot = q.slots[t.target_index]
                slot.payload = t.payload_to_write
                t.state = "RELEASING"
                self.add_log(f"[{t.name}] Wrote payload '{t.payload_to_write}' into Slot {t.target_index} (relaxed).")
                
            elif t.state == "RELEASING":
                slot = q.slots[t.target_index]
                slot.phase_stamp = t.temp_head + 1
                t.state = "IDLE"
                self.add_log(f"[{t.name}] Updated phase_stamp of Slot {t.target_index} to {t.temp_head + 1} (RELEASE).")
                
        else:
            if t.state == "IDLE":
                t.temp_tail = q.tail_index
                t.state = "POLLING"
                self.add_log(f"[{t.name}] Polling slot at tail_index ({t.temp_tail}).")
                
            elif t.state == "POLLING":
                slot_idx = t.temp_tail & BUFFER_MASK
                slot = q.slots[slot_idx]
                if slot.phase_stamp == t.temp_tail + 1:
                    t.state = "CLAIMING"
                    self.add_log(f"[{t.name}] Stamp Match! Slot {slot_idx} is ready for consumption.")
                else:
                    self.add_log(f"[{t.name}] Empty slot / stamp mismatch. Consumer spinning...")
                    t.state = "IDLE"
                    
            elif t.state == "CLAIMING":
                if q.tail_index == t.temp_tail:
                    q.tail_index += 1
                    t.target_index = t.temp_tail & BUFFER_MASK
                    t.state = "READING"
                    self.add_log(f"[{t.name}] CAS Success! Claimed tail slot {t.target_index}.")
                else:
                    self.add_log(f"[{t.name}] CAS Failed! tail_index claimed. Retrying...")
                    t.state = "IDLE"
                    
            elif t.state == "READING":
                slot = q.slots[t.target_index]
                t.payload_read = slot.payload
                t.state = "FREEING"
                self.add_log(f"[{t.name}] Read payload '{t.payload_read}' from Slot {t.target_index}.")
                
            elif t.state == "FREEING":
                slot = q.slots[t.target_index]
                slot.payload = None
                slot.phase_stamp = t.temp_tail + BUFFER_SIZE
                t.state = "IDLE"
                self.add_log(f"[{t.name}] Released Slot {t.target_index} back to producers (Stamp -> {t.temp_tail + BUFFER_SIZE}).")

    def draw_canvas(self):
        center_x, center_y = 180, 180
        ring_radius, slot_radius = 110, 28
        
        ui.set_color('#2c2c2e')
        path = ui.Path.oval(center_x - ring_radius, center_y - ring_radius, ring_radius * 2, ring_radius * 2)
        path.line_width = 4
        path.stroke()
        
        for i in range(BUFFER_SIZE):
            angle = (2 * math.pi / BUFFER_SIZE) * i - math.pi / 2
            sx = center_x + ring_radius * math.cos(angle)
            sy = center_y + ring_radius * math.sin(angle)
            
            slot = self.queue.slots[i]
            ui.set_color('#34c759' if slot.payload else '#1c1c1e')
            
            slot_path = ui.Path.oval(sx - slot_radius, sy - slot_radius, slot_radius * 2, slot_radius * 2)
            slot_path.fill()
            
            ui.set_color('#8e8e93')
            slot_path.line_width = 1.5
            slot_path.stroke()
            
            ui.draw_string(f"[{i}]", (sx - slot_radius, sy - 22, slot_radius * 2, 12), font=('HelveticaNeue-Bold', 10), color='#8e8e93', alignment=ui.ALIGN_CENTER)
            ui.draw_string(f"S:{slot.phase_stamp}", (sx - slot_radius, sy - 6, slot_radius * 2, 12), font=('HelveticaNeue', 10), color='#ffffff', alignment=ui.ALIGN_CENTER)
            p_text = f"{slot.payload}" if slot.payload else "-"
            ui.draw_string(p_text, (sx - slot_radius, sy + 10, slot_radius * 2, 12), font=('CourierNewPS-BoldMT', 10), color='#ff9500' if slot.payload else '#4e4e52', alignment=ui.ALIGN_CENTER)

        ui.set_color('#1c1c1e')
        hub_path = ui.Path.oval(center_x - 40, center_y - 40, 80, 80)
        hub_path.fill()
        ui.set_color('#3a3a3c')
        hub_path.stroke()
        
        ui.draw_string("MPMC", (center_x - 35, center_y - 20, 70, 15), font=('HelveticaNeue-Bold', 11), color='#8e8e93', alignment=ui.ALIGN_CENTER)
        ui.draw_string(f"H:{self.queue.head_index}", (center_x - 35, center_y - 3, 70, 15), font=('HelveticaNeue', 11), color='#ff6b6b', alignment=ui.ALIGN_CENTER)
        ui.draw_string(f"T:{self.queue.tail_index}", (center_x - 35, center_y + 12, 70, 15), font=('HelveticaNeue', 11), color='#4dadf7', alignment=ui.ALIGN_CENTER)

if __name__ == '__main__':
    v = QueueVisualizer()
    v.present('sheet')
