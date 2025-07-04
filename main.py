from typing import List
import components
from ultralytics import YOLO
import cv2
import box
import time
import os
import machine
import hub_dashboard
import product
from Hub import Hub
from productionstep import production_step


def is_significantly_different(set_a, set_b, tolerance):
    return len(set_a.symmetric_difference(set_b)) >= tolerance


base_path = os.path.dirname(__file__)
weights_path = os.path.join(base_path, "weights.pt")
model = YOLO(weights_path)
cap = cv2.VideoCapture(0)
rdy_new = True

if not cap.isOpened():
    print("Cannot open camera")
    exit()
"""
boxes = [box.box([components.component(0, "Anker Typ 7"), components.component(1, "Buerstenhalter"),
                  components.component(2, "Getriebedeckel Typ 6"), components.component(3, "Getriebehause typ 10"),
                  components.component(4, "Getriebehause typ 6"), components.component(5, "Getriebehause typ 9"),
                  components.component(6, "Magnet Lang"), components.component(7, "Poltopf-Lang"),
                  components.component(8, "spange")]),
         box.box([components.component(6, "Magnet Lang"), components.component(7, "Poltopf-Lang"),
                  components.component(8, "spange")])]
"""
machines = [machine.machine(0, "Spritzguss Maschine", "Herstellung der Gehäuse für das Motorgetriebe", "offline"),
            machine.machine(1, "Kupferwickelmaschine", "Wicklung der Kupferdrähte für den Rotor", "offline", )]

boxes = []
seen_classes = set()
photo_counter = 0
last_photo_time = 0
photo_interval = 3

# Create machines exactly as in main.py
m = [
    machine.machine(0, "Spritzguss Maschine", "Herstellung der Gehäuse für das Motorgetriebe", "offline"),
    machine.machine(1, "Kupferwickelmaschine", "Wicklung der Kupferdrähte für den Rotor", "offline")
]

# Create production steps with needed components
production_steps = [
    production_step("Spritzguss Getriebegehäuse", "Spritzguss der Getriebegehäuseteile", machines[0],
                    [components.component(0, "Anker Typ 7"), components.component(1, "Buerstenhalter"),
                     components.component(2, "Getriebedeckel Typ 6")]),
    production_step("Rotorwicklung", "Kupferwicklung des Rotors für den Motor", machines[1],
                    [components.component(0, "Anker Typ 7"), components.component(1, "Buerstenhalter"),
                     components.component(2, "Getriebedeckel Typ 6")])
]

# Create products exactly as in main.py
products_in_production = [
    product.product("Motorgetriebe", production_steps,
                    [components.component(0, "Anker Typ 7"), components.component(1, "Buerstenhalter"),
                     components.component(2, "Getriebedeckel Typ 6")])
]

# Create Hub0 exactly as in main.py
hub0 = Hub("0", m, [], boxes, [], products_in_production)
dashboard = hub_dashboard.HubDashboard(hub0)

while True:
    dashboard.run()
    ret, frame = cap.read()
    if not ret:
        print("Cannot read camera")
        break

    results = model(frame)
    annotated_frame = results[0].plot()

    # Define your capture‐zone as a vertical band in the middle:
    h, w = frame.shape[:2]
    y_min, y_max = int(h * 0.45), int(h * 0.55)  # e.g. middle 10% of height
    x_min, x_max = int(w * 0.30), int(w * 0.70)  # optional: also restrict horizontally

    xyxy = results[0].boxes.xyxy.cpu().numpy()  # shape: (N,4) as [x1, y1, x2, y2]
    valid_idx = []
    for i, (x1, y1, x2, y2) in enumerate(xyxy):
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if (x_min < cx < x_max) and (y_min < cy < y_max):
            valid_idx.append(i)

    # Only keep detections that are “under” the camera
    if not valid_idx:
        current_classes = set()
    else:
        cls = results[0].boxes.cls.cpu().numpy().astype(int)
        current_classes = set(cls[valid_idx])

    key = cv2.waitKey(1) & 0xFF
    new_classes = current_classes - seen_classes

    if current_classes:
        rdy_new = True

    current_time = time.time()
    if is_significantly_different(current_classes, seen_classes, tolerance=1) & rdy_new:
        if current_time - last_photo_time >= photo_interval:
            class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
            class_names = [model.names[c] for c in class_ids]

            comps: List['components'] = []
            for class_id in class_ids:
                name = model.names[class_id]
                comps.append(components.component(class_id, name))

            if len(comps) > 0:
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = f"photo_{timestamp}_{photo_counter}.jpg"
                cv2.imwrite(filename, frame)
                print(f"[+] Neues Objekt erkannt, Foto gespeichert als {filename}")
                photo_counter += 1
                hub0.add_to_q(box.box(comps))

            last_photo_time = current_time
            rdy_new = False

        rdy_new = False

    seen_classes = current_classes

    cv2.imshow("YOLOv8 Live", annotated_frame)
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
