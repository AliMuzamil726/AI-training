"""
Script Splitter - GUI App
--------------------------
Apna lamba script paste karein, "Split into Parts" dabayein, aur
har part ko ek click se copy karein. Sirf sentence/paragraph ke
end (full stop) par cut hota hai - kisi bhi word ki spelling ya
wording change nahi hoti.

Run:
    python script_splitter.py
"""

import re
import tkinter as tk
from tkinter import scrolledtext, messagebox


# ----------------------------------------------------------------------
# Splitting logic (no wording changed, only sliced at sentence ends)
# ----------------------------------------------------------------------

def split_into_sentences(text):
    paragraphs = re.split(r'\n\s*\n', text.strip())
    all_sentences = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        sentences = re.split(r'(?<=[.!?])\s+', para)
        for i, s in enumerate(sentences):
            s = s.strip()
            if not s:
                continue
            is_para_end = (i == len(sentences) - 1)
            all_sentences.append((s, is_para_end))
    return all_sentences


def make_chunks(text, min_words=200, max_words=250):
    sentences = split_into_sentences(text)
    chunks = []
    current = []
    current_word_count = 0

    for sent, is_para_end in sentences:
        word_count = len(sent.split())

        if word_count > max_words:
            if current:
                chunks.append(' '.join(current))
                current = []
                current_word_count = 0
            chunks.append(sent)
            continue

        if current_word_count == 0 or current_word_count + word_count <= max_words:
            current.append(sent)
            current_word_count += word_count

            if current_word_count >= max_words:
                chunks.append(' '.join(current))
                current = []
                current_word_count = 0
            elif current_word_count >= min_words and is_para_end:
                chunks.append(' '.join(current))
                current = []
                current_word_count = 0
        else:
            chunks.append(' '.join(current))
            current = [sent]
            current_word_count = word_count
            if current_word_count >= max_words:
                chunks.append(' '.join(current))
                current = []
                current_word_count = 0

    if current:
        chunks.append(' '.join(current))

    return chunks


# ----------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------

class ScriptSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Script Splitter (200-250 words per part)")
        self.root.geometry("950x750")
        self.root.configure(bg="#1e1e2e")

        self.parts = []
        self.part_frames = []

        self._build_input_section()
        self._build_output_section()

    # ---------------- Input section ----------------
    def _build_input_section(self):
        top_frame = tk.Frame(self.root, bg="#1e1e2e")
        top_frame.pack(fill="x", padx=15, pady=(15, 5))

        tk.Label(
            top_frame,
            text="Apna script yahan paste karein:",
            bg="#1e1e2e",
            fg="#ffffff",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        self.input_box = scrolledtext.ScrolledText(
            self.root,
            height=10,
            wrap="word",
            font=("Segoe UI", 11),
            bg="#2a2a3c",
            fg="#ffffff",
            insertbackground="#ffffff",
        )
        self.input_box.pack(fill="both", expand=False, padx=15, pady=5)

        controls = tk.Frame(self.root, bg="#1e1e2e")
        controls.pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(controls, text="Min words:", bg="#1e1e2e", fg="#ffffff").pack(side="left")
        self.min_var = tk.StringVar(value="200")
        tk.Entry(controls, textvariable=self.min_var, width=6).pack(side="left", padx=(5, 15))

        tk.Label(controls, text="Max words:", bg="#1e1e2e", fg="#ffffff").pack(side="left")
        self.max_var = tk.StringVar(value="250")
        tk.Entry(controls, textvariable=self.max_var, width=6).pack(side="left", padx=(5, 15))

        split_btn = tk.Button(
            controls,
            text="Split into Parts",
            command=self.on_split,
            bg="#89b4fa",
            fg="#1e1e2e",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=15,
            pady=4,
            cursor="hand2",
        )
        split_btn.pack(side="left", padx=10)

        clear_btn = tk.Button(
            controls,
            text="Clear All",
            command=self.on_clear,
            bg="#f38ba8",
            fg="#1e1e2e",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=15,
            pady=4,
            cursor="hand2",
        )
        clear_btn.pack(side="left")

        self.status_label = tk.Label(
            controls, text="", bg="#1e1e2e", fg="#a6e3a1", font=("Segoe UI", 10)
        )
        self.status_label.pack(side="left", padx=15)

    # ---------------- Output section (scrollable) ----------------
    def _build_output_section(self):
        tk.Label(
            self.root,
            text="Parts (har part ke saath copy button):",
            bg="#1e1e2e",
            fg="#ffffff",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=15, pady=(5, 0))

        outer = tk.Frame(self.root, bg="#1e1e2e")
        outer.pack(fill="both", expand=True, padx=15, pady=10)

        self.canvas = tk.Canvas(outer, bg="#1e1e2e", highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#1e1e2e")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ---------------- Actions ----------------
    def on_clear(self):
        self.input_box.delete("1.0", "end")
        for frame in self.part_frames:
            frame.destroy()
        self.part_frames = []
        self.parts = []
        self.status_label.config(text="")

    def on_split(self):
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Khali script", "Pehle script paste karein.")
            return

        try:
            min_words = int(self.min_var.get())
            max_words = int(self.max_var.get())
        except ValueError:
            messagebox.showerror("Galat number", "Min/Max words mein sirf numbers likhein.")
            return

        if min_words <= 0 or max_words <= 0 or min_words > max_words:
            messagebox.showerror("Galat range", "Min words, Max words se chota ya barabar hona chahiye.")
            return

        self.parts = make_chunks(text, min_words, max_words)

        # safety check: ensure no word was changed/lost
        original_words = text.split()
        rebuilt_words = ' '.join(self.parts).split()
        if original_words != rebuilt_words:
            messagebox.showwarning(
                "Warning",
                "Kuch farq mila reconstruction mein - dobara check kar lein.",
            )

        self.render_parts()
        self.status_label.config(
            text=f"{len(self.parts)} parts ban gaye | Total words: {len(original_words)}"
        )

    def render_parts(self):
        for frame in self.part_frames:
            frame.destroy()
        self.part_frames = []

        for idx, part in enumerate(self.parts, start=1):
            word_count = len(part.split())

            frame = tk.Frame(self.scrollable_frame, bg="#2a2a3c", bd=1, relief="solid")
            frame.pack(fill="x", pady=6, padx=2)

            header = tk.Frame(frame, bg="#2a2a3c")
            header.pack(fill="x", padx=8, pady=(6, 2))

            tk.Label(
                header,
                text=f"Part {idx}  ({word_count} words)",
                bg="#2a2a3c",
                fg="#89b4fa",
                font=("Segoe UI", 10, "bold"),
            ).pack(side="left")

            copy_btn = tk.Button(
                header,
                text="Copy",
                command=lambda p=part, i=idx: self.copy_part(p, i),
                bg="#a6e3a1",
                fg="#1e1e2e",
                font=("Segoe UI", 9, "bold"),
                relief="flat",
                padx=10,
                cursor="hand2",
            )
            copy_btn.pack(side="right")

            text_widget = tk.Text(
                frame,
                height=6,
                wrap="word",
                font=("Segoe UI", 10),
                bg="#1e1e2e",
                fg="#cdd6f4",
                relief="flat",
                padx=8,
                pady=6,
            )
            text_widget.insert("1.0", part)
            text_widget.configure(state="disabled")
            text_widget.pack(fill="x", padx=8, pady=(0, 8))

            self.part_frames.append(frame)

    def copy_part(self, text, idx):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()  # keep clipboard data after window closes
        self.status_label.config(text=f"Part {idx} copy ho gaya!")


if __name__ == "__main__":
    root = tk.Tk()
    app = ScriptSplitterApp(root)
    root.mainloop()
