"""
CustomTkinter Desktop GUI for Colab-to-Obsidian AI Knowledge Agent.

Features:
  - Dual Mode: Single Notebook (.ipynb) vs Batch Folder (Recursive)
  - Automatic exercise-solution notebook pairing
  - Smart vault subfolder suggestion with Browse override
  - Base64 plot extraction to 99_Assets/ with Obsidian embedding
  - Intelligent in-place sectional merge vs new note creation
  - Live progress bar, status notifications, and scrolling log console
  - Open Note & Open Vault Folder actions upon completion
  - Fully threaded background processing for a smooth UI
"""

import os
import subprocess
import threading
import traceback
from pathlib import Path
from tkinter import filedialog
from typing import List, Optional

import customtkinter as ctk

from core.ai_client import AzureAIClient
from core.diff_merger import perform_intelligent_merge
from core.file_manager import (
    get_last_notebook_folder,
    get_last_vault_folder,
    is_notebook_processed,
    load_config,
    record_processed_notebook,
    save_config,
    save_extracted_images,
    save_note,
    set_last_notebook_folder,
    set_last_vault_folder,
)
from core.notebook_parser import (
    build_dual_ingestion_payload,
    find_notebook_pairs,
    get_file_hash,
    parse_notebook,
)
from core.notes_generator import (
    extract_title_from_notes,
    get_colab_system_prompt,
    sanitize_notes,
)
from core.vault_scanner import (
    find_matching_note,
    get_default_vault_path,
    get_vault_subfolders,
    suggest_target_subfolder,
)

# Theme configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    """Main Desktop GUI Application."""

    def __init__(self):
        super().__init__()

        # Window setup
        self.title("Colab-to-Obsidian AI Knowledge Agent")
        self.geometry("780x720")
        self.minsize(680, 600)
        self.resizable(True, True)

        # Internal state
        self._is_processing = False
        self._last_result_note: Optional[Path] = None
        self._selected_single_file: Optional[Path] = None
        self._selected_batch_folder: Optional[Path] = None
        self._ai_client: Optional[AzureAIClient] = None

        self._build_ui()
        self._init_defaults()

    def _build_ui(self):
        """Construct GUI widgets."""
        # Main padding container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=24, pady=18)

        # Header
        header_title = ctk.CTkLabel(
            self.main_frame,
            text="🧠 Colab-to-Obsidian AI Knowledge Agent",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        header_title.pack(pady=(0, 2))

        header_sub = ctk.CTkLabel(
            self.main_frame,
            text="Autonomous CS50-grade Obsidian study notes from Jupyter & Google Colab notebooks",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
        )
        header_sub.pack(pady=(0, 14))

        # Mode selector
        self.mode_selector = ctk.CTkSegmentedButton(
            self.main_frame,
            values=["📓 Single Notebook (.ipynb)", "📁 Batch Folder (Recursive)"],
            command=self._on_mode_changed,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
        )
        self.mode_selector.set("📓 Single Notebook (.ipynb)")
        self.mode_selector.pack(fill="x", pady=(0, 12))

        # Dynamic input container
        self.input_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_container.pack(fill="x", pady=(0, 10))

        # 1. Single Notebook Input Frame
        self.single_frame = ctk.CTkFrame(self.input_container, fg_color="transparent")
        lbl_single = ctk.CTkLabel(
            self.single_frame,
            text="Select Colab / Jupyter Notebook",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        lbl_single.pack(fill="x")

        row_single = ctk.CTkFrame(self.single_frame, fg_color="transparent")
        row_single.pack(fill="x", pady=(4, 2))

        self.single_entry = ctk.CTkEntry(
            row_single,
            placeholder_text="Choose a .ipynb notebook...",
            height=38,
            font=ctk.CTkFont(size=12),
        )
        self.single_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_single = ctk.CTkButton(
            row_single,
            text="Browse...",
            width=90,
            height=38,
            command=self._browse_single_file,
        )
        btn_browse_single.pack(side="right")

        self.single_hint = ctk.CTkLabel(
            self.single_frame,
            text="✨ Auto-detects and pairs companion exercise & solution notebooks",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        )
        self.single_hint.pack(fill="x")
        self.single_frame.pack(fill="x")

        # 2. Batch Folder Input Frame
        self.batch_frame = ctk.CTkFrame(self.input_container, fg_color="transparent")
        lbl_batch = ctk.CTkLabel(
            self.batch_frame,
            text="Select Folder Containing Notebooks",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        lbl_batch.pack(fill="x")

        row_batch = ctk.CTkFrame(self.batch_frame, fg_color="transparent")
        row_batch.pack(fill="x", pady=(4, 2))

        self.batch_entry = ctk.CTkEntry(
            row_batch,
            placeholder_text="Choose folder to scan recursively...",
            height=38,
            font=ctk.CTkFont(size=12),
        )
        self.batch_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_batch = ctk.CTkButton(
            row_batch,
            text="Browse...",
            width=90,
            height=38,
            command=self._browse_batch_folder,
        )
        btn_browse_batch.pack(side="right")

        self.skip_processed_cb = ctk.CTkCheckBox(
            self.batch_frame,
            text="Skip already processed notebooks (via tracker.json checkpoint)",
            font=ctk.CTkFont(size=11),
        )
        self.skip_processed_cb.select()
        self.skip_processed_cb.pack(anchor="w", pady=(2, 0))

        # Vault Destination Selector
        lbl_vault = ctk.CTkLabel(
            self.main_frame,
            text="Obsidian Vault Destination",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        lbl_vault.pack(fill="x", pady=(4, 0))

        row_vault = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row_vault.pack(fill="x", pady=(4, 6))

        self.vault_entry = ctk.CTkEntry(
            row_vault,
            placeholder_text="Target Obsidian Vault / Subfolder...",
            height=38,
            font=ctk.CTkFont(size=12),
        )
        self.vault_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_vault = ctk.CTkButton(
            row_vault,
            text="Browse...",
            width=90,
            height=38,
            command=self._browse_vault_folder,
        )
        btn_browse_vault.pack(side="right")

        # Options Row
        row_opts = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row_opts.pack(fill="x", pady=(0, 10))

        self.merge_cb = ctk.CTkCheckBox(
            row_opts,
            text="Intelligent in-place merge if matching topic note exists in vault",
            font=ctk.CTkFont(size=12),
        )
        self.merge_cb.select()
        self.merge_cb.pack(side="left")

        # Action Button: Create Notes
        self.btn_create = ctk.CTkButton(
            self.main_frame,
            text="🚀  Create Obsidian Study Notes",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_processing,
        )
        self.btn_create.pack(fill="x", pady=(2, 10))

        # Status and Progress Area
        status_box = ctk.CTkFrame(self.main_frame)
        status_box.pack(fill="both", expand=True)

        self.lbl_status = ctk.CTkLabel(
            status_box,
            text="Status: Ready",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        self.lbl_status.pack(fill="x", padx=14, pady=(8, 2))

        self.progress_bar = ctk.CTkProgressBar(status_box)
        self.progress_bar.pack(fill="x", padx=14, pady=(0, 6))
        self.progress_bar.set(0)

        self.log_console = ctk.CTkTextbox(
            status_box,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
        )
        self.log_console.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        # Action Buttons Row (Initially disabled/hidden until complete)
        self.actions_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.actions_row.pack(fill="x", pady=(8, 0))

        self.btn_open_note = ctk.CTkButton(
            self.actions_row,
            text="📖 Open Note",
            width=140,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2b7a4b",
            hover_color="#1e5c36",
            command=self._open_note,
        )
        self.btn_open_note.pack(side="left", padx=(0, 8))
        self.btn_open_note.configure(state="disabled")

        self.btn_open_folder = ctk.CTkButton(
            self.actions_row,
            text="📂 Open Vault Folder",
            width=160,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3a5a80",
            hover_color="#2a4260",
            command=self._open_vault_folder,
        )
        self.btn_open_folder.pack(side="left")
        self.btn_open_folder.configure(state="disabled")

    def _init_defaults(self):
        """Set default initial folder values from config or system discovery."""
        last_vault = get_last_vault_folder()
        self.vault_entry.insert(0, last_vault)

        last_nb_folder = get_last_notebook_folder()
        self.batch_entry.insert(0, last_nb_folder)

        self._log("System initialized. Target Vault: " + last_vault)
        self._log("Azure OpenAI Deployment: gpt-5-mini (Active)")

    def _log(self, message: str):
        """Append a message to the live log console."""
        self.log_console.insert("end", f"{message}\n")
        self.log_console.see("end")

    def _set_status(self, text: str):
        """Update status label safely."""
        self.lbl_status.configure(text=f"Status: {text}")

    def _on_mode_changed(self, value: str):
        """Toggle between single file and batch folder views."""
        if "Single" in value:
            self.batch_frame.pack_forget()
            self.single_frame.pack(fill="x")
        else:
            self.single_frame.pack_forget()
            self.batch_frame.pack(fill="x")

    def _browse_single_file(self):
        """Open file dialog for choosing a single .ipynb file."""
        init_dir = get_last_notebook_folder()
        chosen = filedialog.askopenfilename(
            title="Select Notebook File",
            initialdir=init_dir,
            filetypes=[("Jupyter Notebooks", "*.ipynb"), ("All Files", "*.*")],
        )
        if chosen:
            p = Path(chosen)
            self._selected_single_file = p
            self.single_entry.delete(0, "end")
            self.single_entry.insert(0, str(p))
            set_last_notebook_folder(str(p.parent))

            # Auto-suggest subfolder if vault is default
            self._auto_route_vault(p.stem)

    def _browse_batch_folder(self):
        """Open folder dialog for choosing folder of notebooks."""
        init_dir = get_last_notebook_folder()
        chosen = filedialog.askdirectory(
            title="Select Folder Containing Notebooks",
            initialdir=init_dir,
        )
        if chosen:
            p = Path(chosen)
            self._selected_batch_folder = p
            self.batch_entry.delete(0, "end")
            self.batch_entry.insert(0, str(p))
            set_last_notebook_folder(str(p))

    def _browse_vault_folder(self):
        """Open folder dialog for selecting Obsidian Vault / subfolder."""
        init_dir = self.vault_entry.get().strip() or str(get_default_vault_path())
        chosen = filedialog.askdirectory(
            title="Select Target Vault Folder",
            initialdir=init_dir,
        )
        if chosen:
            self.vault_entry.delete(0, "end")
            self.vault_entry.insert(0, chosen)
            set_last_vault_folder(chosen)

    def _auto_route_vault(self, notebook_stem: str):
        """Suggest destination subfolder in vault based on notebook name."""
        current_vault = Path(self.vault_entry.get().strip() or get_default_vault_path())
        suggested = suggest_target_subfolder(current_vault, notebook_stem)
        if suggested.exists() and suggested != current_vault:
            self.vault_entry.delete(0, "end")
            self.vault_entry.insert(0, str(suggested))
            self._log(f"Auto-suggested target folder: {suggested.name}")

    def _start_processing(self):
        """Validate inputs and launch background worker thread."""
        if self._is_processing:
            return

        vault_path_str = self.vault_entry.get().strip()
        if not vault_path_str or not Path(vault_path_str).exists():
            self._log("❌ Error: Target vault destination folder does not exist.")
            return

        is_single = "Single" in self.mode_selector.get()
        if is_single:
            nb_file_str = self.single_entry.get().strip()
            if not nb_file_str or not Path(nb_file_str).is_file():
                self._log("❌ Error: Please select a valid .ipynb notebook file.")
                return
        else:
            batch_folder_str = self.batch_entry.get().strip()
            if not batch_folder_str or not Path(batch_folder_str).is_dir():
                self._log("❌ Error: Please select a valid notebook folder.")
                return

        # Disable button & start thread
        self._is_processing = True
        self.btn_create.configure(state="disabled", text="⏳ Processing...")
        self.btn_open_note.configure(state="disabled")
        self.btn_open_folder.configure(state="disabled")
        self.progress_bar.set(0.05)

        thread = threading.Thread(target=self._process_worker, daemon=True)
        thread.start()

    def _process_worker(self):
        """Worker thread executing notebook parsing, AI synthesis, and saving."""
        try:
            vault_dest = Path(self.vault_entry.get().strip())
            # Find base vault root for 99_Assets (find directory containing 99_Assets or top-level)
            vault_root = vault_dest
            for parent in [vault_dest] + list(vault_dest.parents):
                if (parent / "99_Assets").exists() or (parent / ".obsidian").exists():
                    vault_root = parent
                    break

            is_single = "Single" in self.mode_selector.get()
            should_merge = bool(self.merge_cb.get())
            skip_processed = bool(self.skip_processed_cb.get())

            if not self._ai_client:
                self._set_status("Initializing Azure OpenAI client...")
                self._ai_client = AzureAIClient()

            if is_single:
                target_file = Path(self.single_entry.get().strip())
                # Discover if this single file has a paired solutions/exercise notebook
                parent_dir = target_file.parent
                all_in_folder = list(parent_dir.glob("*.ipynb"))
                pairs = find_notebook_pairs(all_in_folder)
                
                # Find matching pair entry
                target_pair = None
                for p in pairs:
                    if p["primary_path"] == target_file or p.get("exercise_path") == target_file:
                        target_pair = p
                        break
                if not target_pair:
                    target_pair = {
                        "display_name": target_file.stem.replace("_", " ").title(),
                        "is_pair": False,
                        "exercise_path": None,
                        "solution_path": target_file,
                        "primary_path": target_file,
                    }

                items_to_process = [target_pair]
            else:
                batch_dir = Path(self.batch_entry.get().strip())
                self._set_status(f"Scanning notebooks in {batch_dir.name}...")
                all_nbs = list(batch_dir.glob("**/*.ipynb"))
                items_to_process = find_notebook_pairs(all_nbs)
                self._log(f"Found {len(all_nbs)} notebooks, grouped into {len(items_to_process)} note entities.")

            total_items = len(items_to_process)
            completed_count = 0

            for idx, item in enumerate(items_to_process):
                display_name = item["display_name"]
                primary_file = item["primary_path"]
                exercise_file = item.get("exercise_path")
                solution_file = item.get("solution_path") or primary_file

                file_hash = get_file_hash(primary_file)

                # Check checkpoint
                if not is_single and skip_processed and is_notebook_processed(file_hash):
                    self._log(f"⏭️ Skipping already processed: {display_name}")
                    completed_count += 1
                    self.progress_bar.set(completed_count / total_items)
                    continue

                self._set_status(f"Processing ({idx+1}/{total_items}): {display_name}")
                self._log(f"\n▶ [{idx+1}/{total_items}] Ingesting: {display_name}")
                if item.get("is_pair"):
                    self._log(f"   Paired: {exercise_file.name} ↔ {solution_file.name}")

                # 1. Parse notebooks
                sol_data = parse_notebook(solution_file)
                ex_data = parse_notebook(exercise_file) if exercise_file and exercise_file != solution_file else None

                # 2. Extract and save embedded plot images
                all_images = sol_data["images"] + (ex_data["images"] if ex_data else [])
                if all_images:
                    saved_names = save_extracted_images(all_images, vault_root)
                    self._log(f"   🖼️ Saved {len(saved_names)} plot figures to 99_Assets/")

                # 3. Build unified content payload
                payload = build_dual_ingestion_payload(ex_data, sol_data)

                # 4. Check for existing note in destination for in-place merge
                existing_match = None
                if should_merge:
                    existing_match = find_matching_note(sol_data["suggested_title"], vault_dest)

                if existing_match:
                    self._log(f"   🔄 Matching note detected: '{existing_match.name}'. Performing In-Place Merge...")
                    existing_text = existing_match.read_text(encoding="utf-8")
                    merged_content = perform_intelligent_merge(
                        existing_note_content=existing_text,
                        new_notebook_payload=payload,
                        ai_client=self._ai_client,
                        progress_callback=self._log,
                    )
                    final_path = save_note(
                        folder=vault_dest,
                        filename=existing_match.stem,
                        notes_content=merged_content,
                        source_file=solution_file.name,
                        is_inplace_update=True,
                        existing_file_path=existing_match,
                    )
                    self._log(f"   ✅ Merged & Updated: {final_path.name}")
                else:
                    self._log(f"   ✨ Synthesizing new CS50 study note...")
                    messages = [
                        {"role": "system", "content": get_colab_system_prompt()},
                        {"role": "user", "content": f"Transform this notebook into Obsidian study notes:\n\n{payload}"}
                    ]
                    raw_notes = self._ai_client.generate_chat_completion(
                        messages=messages,
                        progress_callback=self._log,
                    )
                    clean_notes = sanitize_notes(raw_notes)
                    note_title = extract_title_from_notes(clean_notes, fallback=sol_data["suggested_title"])
                    final_path = save_note(
                        folder=vault_dest,
                        filename=note_title,
                        notes_content=clean_notes,
                        source_file=solution_file.name,
                    )
                    self._log(f"   ✅ Created: {final_path.name}")

                # Record checkpoint
                record_processed_notebook(file_hash, solution_file.name, final_path)
                self._last_result_note = final_path

                completed_count += 1
                self.progress_bar.set(completed_count / total_items)

            self._set_status("All notes successfully generated!")
            self._log("\n🎉 Generation complete! Study notes are ready in Obsidian.")
            self.btn_open_note.configure(state="normal")
            self.btn_open_folder.configure(state="normal")

        except Exception as e:
            traceback.print_exc()
            self._set_status(f"Error: {e}")
            self._log(f"\n❌ Error during processing: {e}")
        finally:
            self._is_processing = False
            self.btn_create.configure(state="normal", text="🚀  Create Obsidian Study Notes")

    def _open_note(self):
        """Open the generated note in default markdown editor / Obsidian."""
        if self._last_result_note and self._last_result_note.exists():
            try:
                os.startfile(str(self._last_result_note))
            except Exception as e:
                self._log(f"Could not open file: {e}")

    def _open_vault_folder(self):
        """Open the target vault destination folder in Windows Explorer."""
        vault_dest = Path(self.vault_entry.get().strip())
        if vault_dest.exists():
            try:
                os.startfile(str(vault_dest))
            except Exception as e:
                self._log(f"Could not open folder: {e}")


def launch_app():
    """Launch the CustomTkinter GUI application."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    launch_app()
