# Training data

Use a lawfully obtained road-damage dataset and label it in YOLO format: one `.txt` per image, each row `class x_center y_center width height` normalized from 0 to 1. Populate `dataset/images/{train,val,test}` and matching `dataset/labels/{train,val,test}`, then run `python training/train.py`. Copy `runs/roadvision/train/weights/best.pt` to `backend/models/road_damage.pt` after validation. Evaluate before making performance claims.
