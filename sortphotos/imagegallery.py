import tkinter as tk
from tkinter import ttk
from pathlib import Path
from PIL import Image, ImageTk
from scrollviews import VerticalScrollbarFrame
import json
import dill


class ImageGallery(tk.Tk):
    def __init__(self, image_paths):
        super().__init__()
        self.images = image_paths

        self.ims = []

        self.gallery_frame = VerticalScrollbarFrame(self)
        self.image_frame = self.gallery_frame.content_frame

        self.geometry("1200x900")

        self.setup_gallery(self.images)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.gallery_frame.grid(column=0, row=0, sticky='nesw')
        self.gallery_frame.on_configure()

    def setup_gallery(self, image_paths):
        """
        Fill the scroll canvas with a gallery raster of
        cells.
        """
        col = 0
        for row, image in enumerate(image_paths.items()):
            if not (row % 4) == 0:
                row -= col
            path, caption = image
            cell = self.setup_imagecell(self.image_frame, path, caption)
            self.image_frame.rowconfigure(row, weight=0)

            cell.grid(column=col, row=row, sticky='nesw')
            if col == 0:
                col = 1
            elif col == 1:
                col = 2
            elif col == 2:
                col = 3
            else:
                col = 0

    def setup_imagecell(self, master, image_path, caption):
        cell_frame = tk.Frame(master)
        load = Image.open(Path(image_path))
        load.thumbnail((200,200), Image.ANTIALIAS)
        photo = ImageTk.PhotoImage(load)

        image_lbl = ttk.Label(cell_frame, image=photo)
        image_lbl.image = photo
        image_lbl.grid(column=0, row=0, sticky='nesw')
        self.ims.append(image_lbl)

        caption_lbl = ttk.Label(cell_frame, text=caption)
        caption_lbl.grid(column=0, row=1, sticky='nesw')

        return cell_frame

    def remove_from_storage(self):
        pass

    def readd_to_storage(self):
        pass

    def btn_label(self, master):
        pass

if __name__ == '__main__':

    rel_files = Path("/home/lukas/git/sortphotos").rglob("*leute_tags*")

    tagged_dict = {} # Dict mit path als key und Liste mit Tags als Value
    for path in rel_files:
        print(path.name) # Helps to detect mal formatted input data
        fotos = json.loads(path.read_text())
        for foto in fotos:
            tagged_dict.update(foto)

    one_tag_path_dict = {
        key: value
        for key, value in tagged_dict.items()
        if len(value) == 1
    }

    rel_files = Path("/home/lukas/git/sortphotos").rglob("*oneperson*")
    one_person_dict = {}
    for path in rel_files:
        print(path.name)
        paths = json.loads(path.read_text())
        one_person_dict.update({p: None for p in paths})

    intersect = {key: value[0] for key, value in one_tag_path_dict.items() if key in one_person_dict}

    intersect_store = Path('/home/lukas/git/sortphotos/intersect.dill')
    if intersect_store.exists():
        intersect = dill.loads(intersect_store.read_bytes())
    else:
        intersect_store.write_bytes(dill.dumps(intersect))


    app = ImageGallery(intersect)

    app.mainloop()
