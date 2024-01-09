import time
import threading
import os
from whisper_marker_w import whisper_marker_w
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import tkinter as tk
from tkinter import filedialog
import torch
import stable_whisper
import customtkinter as ctk
from PIL import Image
import json
import socket


                
class whisper_transscriber():
    _instance = None

    def __new__(cls, entities=None, progressbar=None, current_work=None):
        if cls._instance is None:
            cls._instance = super(whisper_transscriber, cls).__new__(cls)
            cls._instance.initialized = False
            cls._instance.initialize_singleton(entities, progressbar, current_work)
            
        return cls._instance
    
    def initialize_singleton(self, entities, progressbar, current_work):
        
        if not self.initialized:
            self.entities = entities
            self.progressbar = progressbar
            self.current_work = current_work
            self.jsonbase = jsonbase()
            self.lock = threading.Lock()
            thread = threading.Thread(target=self.start)
            thread.daemon = True
            thread.start()
            
    def create_model(self):
            
            print("kreere whisper modellen")
            #Sæt device. Brug GPU hvis en GPU med CUDA-mulighed er tilstede, ellers brug CPU
            DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
            #initialisere vores whisper model. Her bruger vi largemodellen. 
            whisper_model = stable_whisper.load_model("large", device=DEVICE)
            
            return whisper_model, "large"
        
        
    def sort_entities_by_prio(self):
        self.entities.sort_by_prio_name()
    
    def get_aud_type(self, path):
        path = path.replace("/", os.path.sep) 
        parts = path.split(os.path.sep)
        second_to_last_part = parts[-2] 
        
        if second_to_last_part == "Sync":
            aud_type = "1"
        elif second_to_last_part == "Reportage":
            aud_type = "2"
        return aud_type
    
    def get_output_folder(self, out_root, path):
        path = path.replace("/", os.path.sep)  
        parts = path.split(os.path.sep)
        out_path_last = os.path.sep.join(parts[-2:])
        output_folder = os.path.join(out_root, out_path_last)
        
        return output_folder
    
    def get_file_type(self, filetype):
        if filetype == "AAF":
            return "1"
        else:
            return "2"
        
    def start(self):
        whisper_model, whisper_model_name = self.create_model()   
        while True:
            try:
                found = False
                with self.lock:
                    self.sort_entities_by_prio()
                    
            
                for entity in self.entities.entity_list:           
                    log_choice = entity.filetype
                    verification_folder = entity.VERIFICATION_DIRECTORY
                    language = entity.language

                         
                    for path, job in entity.get_job_dict().items():
                     
                        if job.job_status == 0:
                            
                            aud_type = self.get_aud_type(job.job_path)
                            prompt = ""
                            input_folder = job.job_path
                            output_folder = self.get_output_folder(entity.FROM_PROLOGUE, job.job_path)
                            print("inden trans: " + str(job.job_status))
                            # Job status reminder: 0 = queued, 1 = in progress, 2 = complete, 3 = failed
                            job.update_job_status(1)
                            jsonbase.update_job_status(entity.name, job.job_path, 1)
                            print("after in progress: " + str(job.job_status))

                            w_runner = whisper_marker_w(log_choice, aud_type, prompt, language, self.progressbar, self.current_work, 
                                                        input_folder, output_folder, verification_folder, whisper_model, whisper_model_name)
                            completion_status = w_runner.status
                            
                            time.sleep(10)
                            
                            jsonbase.update_job_status(entity.name, job.job_path, completion_status)
                            job.update_job_status(completion_status)
                            print("efter trans: " + str(job.job_status))
                            
                            found = True
                            break
                        
                    if found == True:
                        break
                if found == False:
                    time.sleep(20)
                
            except Exception as e:
                if "'NoneType' object is not iterable" in str(e):
                    print("entities are empty. trying again in 60 seconds.")
                    time.sleep(60)
                else:
                    print("start:")
                    print(e)

class watchfolder_entity_container():
    _instance = None

    def __new__(cls, parent=None):
        if cls._instance is None:
            cls._instance = super(watchfolder_entity_container, cls).__new__(cls)
            cls._instance.initialized = False
            cls._instance.initialize_singleton(parent)
            
        return cls._instance

    def initialize_singleton(self, parent):
        if not self.initialized:
            self.parent = parent
            self.entity_list = []
            self.json = jsonbase()
            self.get_data_from_json()
            self.sort_by_name()
            self.show_entities()
            self.initialized = True
        
    def append_entity(self, name, path, filetype, language, prio):
        entity = watchfolder_entity(self.parent, name, path, filetype, language, prio)
        self.json.add_entity(name, path, filetype, language, prio)
        self.entity_list.append(entity)
        self.sort_by_name()
        self.show_entities()
    
    def get_data_from_json(self):
        self.entity_list.extend(self.json.get_entity_objects(self.parent))
        
    def sort_by_prio_name_key(self, obj):
        prio_order = {"LOW": 2, "MEDIUM": 1, "HIGH": 0}
        prio_value = prio_order.get(obj.prio, 3) 

        return (prio_value, obj.name)

    
    def sort_by_prio_name(self):
        sorted_entities = sorted(self.entity_list, key=self.sort_by_prio_name_key)
        self.entity_list = sorted_entities
    
    def sort_by_name(self):
        self.entity_list.sort(key=lambda entity: entity.name)
    
    def show_entities(self):
        for entity in self.entity_list:
            entity.entity_frame.update()
            if not entity.entity_frame.winfo_ismapped():
                entity.entity_frame.pack(fill="x", padx=7, pady=10, expand=True)
            else:
                entity.entity_frame.forget()
                entity.entity_frame.pack(fill="x", padx=7, pady=10, expand=True)
            
            
class watchfolder_entity():

    def __init__(self, parent, name, path, filetype, language, prio):
        
        self.parent = parent
        self.name = name
        self.path = path
        self.filetype = filetype
        self.language = language
        self.prio = prio
        self.watcher = watchfolder_assigner(self.path)
        self.jsonbase = jsonbase()
        self.lock = threading.Lock()
        
        self.create_entity_watchfolders_from_path(self.path)
        self.build_entity()
        self.watchfolder_jobs = watchfolder_job_container(self.entity_folder_list_container_frame)
    
    
    def get_job_dict(self):
        return self.watchfolder_jobs.job_dict
    
    #TODO
    def check_if_correct_filestructure_for_filetype(self):
        pass
    
    def check_for_new_jobs(self):
        try:
            jobs = self.watcher.get_checked_directories()
            
            for job, job_status in jobs.items():
                jobname = os.path.basename(job)
                
                
                if job not in self.watchfolder_jobs.job_dict:
                    # Job status set as "queued" when first added
                    # Job status reminder: 0 = queued, 1 = in progress, 2 = complete, 3 = failed, 4 = wrong file structure
                    self.jsonbase.add_job(self.name, job_status, jobname, job)
                    with self.lock:
                        self.watchfolder_jobs.append_job(job_status, jobname, job)
            
            # Remove jobs that are not in new_jobs
            existing_jobs = list(self.watchfolder_jobs.job_dict.keys())  # Get the keys (job paths) from the dictionary
            jobs_to_remove = [job for job in existing_jobs if job not in jobs.keys()]
            
            for job_to_remove in jobs_to_remove:
                # Remove the job from the dictionary
                self.watchfolder_jobs.job_dict[job_to_remove].job_frame.destroy()
                self.watchfolder_jobs.job_dict.pop(job_to_remove)
                
        except Exception as e:
            print(f"Exception in start_watching: {e}")
        
        self.entity_folder_list_container_frame.after(1000, self.check_for_new_jobs)
                    
        
    def build_entity(self):
        #gcd = greatest common divisor of opened height and closed height
        gcd = 2
        self.speed = gcd * 30
        self.opened_height = 300
        self.closed_height = 58
        
        self.entity_frame = ctk.CTkFrame(self.parent, bg_color="#999999", fg_color="#999999", height=self.closed_height)
        self.entity_frame.pack_propagate(False)
        self.is_closed = True
        #info frame
        self.entity_info_frame = ctk.CTkFrame(self.entity_frame, bg_color="transparent", fg_color="transparent")
        self.entity_info_frame.pack(fill="x")
        
        self.entity_info_queuedcompleted_frame = ctk.CTkFrame(self.entity_info_frame, bg_color="transparent", fg_color="transparent")
        self.entity_info_queuedcompleted_frame.pack(side="right")
        
        #info frame - queue/completed/button
        queuedcompleted_padx=15
        mtg_sans_bold_font= ctk.CTkFont(family='MTG Sans', size=17, weight='bold')
        
        self.entity_info_queued_var = tk.StringVar()
        self.entity_info_queued = ctk.CTkLabel(self.entity_info_queuedcompleted_frame, font=mtg_sans_bold_font,
                                                           image=ctk.CTkImage(light_image=Image.open("media/Collapsed WF - queued.png"), size=(130,25)),
                                                           textvariable=self.entity_info_queued_var, text_color="white", compound="left", bg_color="transparent")
        self.entity_info_queued.grid(column=0, row=0, sticky="e", padx=queuedcompleted_padx, pady=(2,0))
        
        self.entity_info_completed_var = tk.StringVar()
        self.entity_info_completed = ctk.CTkLabel(self.entity_info_queuedcompleted_frame, font=mtg_sans_bold_font,
                                                           image=ctk.CTkImage(light_image=Image.open("media/Collapsed WF - completed.png"),size=(159,25)),
                                                           textvariable=self.entity_info_completed_var, text_color="white", compound="left", bg_color="transparent")
        
        self.entity_info_completed.grid(column=0,row=1, sticky="e", padx=queuedcompleted_padx)
        
        self.entity_open_button = label_image_button(
                                  frame=self.entity_info_queuedcompleted_frame,
                                  images=("media/EXPAND SYMBOL.png",
                                          "media/EXPAND SYMBOL.png",
                                          "media/COLLAPSE SYMBOL.png"
                                          ),
                                  size=(48,48),
                                  command=self.animate,
                                  highlight=False
                                  )
        
        self.entity_open_button.grid_button(column=1, row=0, rowspan=2, padx=queuedcompleted_padx)

        #info frame - path/project/prio
        self.entity_info_details_frame = ctk.CTkFrame(self.entity_info_frame, bg_color="transparent", fg_color="transparent")
        self.entity_info_details_frame.pack(side="left", fill="both", expand=True)
        self.entity_info_details_frame.grid_rowconfigure(0, weight=1)
        
        
        
        self.entity_info_details_path = ctk.CTkLabel(self.entity_info_details_frame, font=mtg_sans_bold_font,
                                                           image=ctk.CTkImage(light_image=Image.open("media/Collapsed WF - Path.png"),size=(60,26)),
                                                           text=self.path, text_color="#FFFFFF", compound="top", bg_color="transparent", 
                                                           )
        
        self.entity_info_details_path.grid(column=0, row=0, sticky="nsew")

        self.entity_info_details_proj = ctk.CTkLabel(self.entity_info_details_frame, font=mtg_sans_bold_font,
                                                           image=ctk.CTkImage(light_image=Image.open("media/Collapsed WF - Project.png"),size=(85,26)),
                                                           text=self.name, text_color="#FFFFFF", compound="top", bg_color="transparent", 
                                                           )
        self.entity_info_details_proj.grid(column=1, row=0, sticky="nsew")

        self.entity_info_details_prio = ctk.CTkLabel(self.entity_info_details_frame, font=mtg_sans_bold_font,
                                                           image=ctk.CTkImage(light_image=Image.open("media/Collapsed WF - Priority.png"),size=(89,26)),
                                                           text=self.prio, text_color="#FFFFFF", compound="top", bg_color="transparent", 
                                                           )
        self.entity_info_details_prio.grid(column=2, row=0, sticky="nsew")
        
        self.set_column_widths(3)
        
        #folder list frame
        self.entity_folder_list_frame = ctk.CTkFrame(self.entity_frame, bg_color="transparent", fg_color="transparent")
        self.entity_folder_list_frame.place(relx=0, rely=0.09, relwidth=1, relheight=0.95)
        
        self.entity_folder_list_container_frame = ctk.CTkScrollableFrame(self.entity_folder_list_frame, bg_color="#AEAEAE", fg_color="#AEAEAE")
        self.entity_folder_list_container_frame.place(relx=0.01, rely=0.10, relwidth=0.95, relheight=0.84)
        
        self.watcher.assign_watcher_to_entity()

        self.entity_folder_list_container_frame.after(1000, self.check_for_new_jobs)
        
        #move info frame to top
        self.entity_info_frame.lift()
        
    def create_entity_watchfolders_from_path(self, path):
        # Define the paths
        IN_SYNC_DIRECTORY = os.path.join(path, "To Prologue", "Sync")
        IN_REPORTAGE_DIRECTORY = os.path.join(path, "To Prologue", "Reportage")
        OUT_SYNC_DIRECTORY = os.path.join(path, "From Prologue", "Sync")
        OUT_REPORTAGE_DIRECTORY = os.path.join(path, "From Prologue", "Reportage")
        self.VERIFICATION_DIRECTORY = os.path.join(path, "To Prologue", "Verification")
        self.FROM_PROLOGUE = os.path.join(path, "From Prologue")
        
        # Check and create directories if they don't exist
        for directory in [IN_SYNC_DIRECTORY, IN_REPORTAGE_DIRECTORY, OUT_SYNC_DIRECTORY, OUT_REPORTAGE_DIRECTORY, self.VERIFICATION_DIRECTORY]:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                    print(f"Created directory: {directory}")
                except Exception as e:
                    print(f"Failed to create directory: {directory}\nError: {str(e)}")
                    
    def set_column_widths(self, num_columns):

        for column in range(num_columns):
            self.entity_info_details_frame.grid_columnconfigure(column, weight=1)
            
    def animate(self):
        if self.is_closed:
            self.entity_open_button.set_button_active()
            self.animate_open()
        else:
            self.entity_open_button.set_button_default()
            self.animate_close()
            
    def animate_open(self):
        current_height = self.entity_frame.winfo_height()
        if current_height < self.opened_height:
            self.entity_frame.configure(height=current_height + self.speed)
            self.entity_frame.after(10, self.animate_open)
        else:
            self.is_closed = False
        
    
    def animate_close(self):
        current_height = self.entity_frame.winfo_height()
        if current_height > self.closed_height:
            self.entity_frame.configure(height=current_height - self.speed)
            self.entity_frame.after(10, self.animate_close)
        else:
            self.is_closed = True
            self.entity_folder_list_frame.configure(bg_color="transparent", fg_color="transparent")
        
class directory_handler(FileSystemEventHandler):
    def __init__(self, paths_to_watch):
        self.lock = threading.Lock()
        self.new_directories = []
        self.checked_directories = {}
        self.check_interval = 10
        self.paths_to_watch = paths_to_watch
        self.jsonbase = jsonbase()

    def on_moved(self, event):
        if event.is_directory:
            with self.lock:
                old_path = event.src_path
                new_path = event.dest_path

                if old_path in self.new_directories:

                        self.new_directories.remove(old_path)
                        self.new_directories.append(new_path)
                        print(f"Moved and updated in {self.new_directories}: {old_path} -> {new_path}")
                
                if old_path in self.checked_directories:

                        
                        job_status = self.jsonbase.get_job_status(old_path)
                        self.checked_directories.pop(old_path)
                        self.jsonbase.remove_job(old_path)
                        
                        self.checked_directories[new_path] = job_status
                        print(f"Moved and updated in {self.checked_directories}: {old_path} -> {new_path}")

            
    def on_created(self, event):
        if event.is_directory:
            with self.lock:
                directory_path = event.src_path
                self.new_directories.append(directory_path)
                print(f"New directory created: {directory_path}")
                print("Temporary List:", self.new_directories)
                print("Checked List:", self.checked_directories)

    def check_directories(self):
        while True:
            current_time = time.time()

            for directory_path in self.new_directories[:]:
                if os.path.exists(directory_path):
                    # Get the last modification time of the directory
                    last_modified_time = os.path.getmtime(directory_path)

                    # Calculate the time elapsed since the last modification
                    time_elapsed = current_time - last_modified_time

                    # If no changes have been made within the last 10 seconds, move to checked_directories
                    if time_elapsed >= self.check_interval:
                        
                            self.checked_directories[directory_path] = 0
                            self.new_directories.remove(directory_path)
                            print(f"Directory '{directory_path}' checked and moved to checked_directories.")
                            print("Temporary List:", self.new_directories)
                            print("Checked List:", self.checked_directories)
                else:
                    # If the directory no longer exists, remove it from new_directories
                    
                        self.new_directories.remove(directory_path)
                        self.jsonbase.remove_job(directory_path)
                        print(f"Directory '{directory_path}' no longer exists. Removed from new_directories.")
                        print("Temporary List:", self.new_directories)
                        print("Checked List:", self.checked_directories)


            for directory_path in list(self.checked_directories.keys()):
                    if not os.path.exists(directory_path):
                        self.checked_directories.pop(directory_path)
                        self.jsonbase.remove_job(directory_path)
                        print(f"Directory '{directory_path}' no longer exists. Removed from checked_directories.")
                        print("Temporary List:", self.new_directories)
                        print("Checked List:", self.checked_directories)


            time.sleep(self.check_interval)

class watchfolder_assigner():
    
    def __init__(self, parent_path):
        sync = os.path.join(parent_path, "To Prologue/Sync")
        reportage = os.path.join(parent_path, "To Prologue/Reportage")
        self.paths_to_watch = [sync, reportage]
        self.event_handler = directory_handler(self.paths_to_watch)

    def assign_watcher_to_entity(self):
        

        def watch():
            
            observer = Observer()

            paths_to_watch = self.event_handler.paths_to_watch

            for path_to_watch in paths_to_watch:
                observer.schedule(self.event_handler, path_to_watch, recursive=False)

            observer.start()

            try:
                time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
            observer.join()

        watcher_thread = threading.Thread(target=watch)
        watcher_thread.daemon = True
        watcher_thread.start()

        check_directories_thread = threading.Thread(target=self.event_handler.check_directories)
        check_directories_thread.daemon = True
        check_directories_thread.start()

    def get_checked_directories(self):
        return self.event_handler.checked_directories

    def set_checked_directories(self, paths):
        self.event_handler.checked_directories.update(paths)
        
class watchfolder_job_container():
    
    def __init__(self, parent):   
        self.parent=parent
        self.job_dict = {}
        
    def append_job(self, job_name, job_status, job_path):
        # Job status reminder: 0 = queued, 1 = in progress, 2 = complete, 3 = failed, 4 = wrong file structure
        self.job_dict[job_path] = watchfolder_job(self.parent, job_name, job_status, job_path)
        
        
    

                
class watchfolder_job():
    
    def __init__(self, frame, job_status, job_name, job_path):
        # Job status reminder: 0 = queued, 1 = in progress, 2 = complete, 3 = failed, 4 = wrong file structure
        self.job_status = job_status
        self.job_name = job_name
        self.job_path = job_path
        border_width = 2
        corner_radius = 0
        border_color = "#5C5C5C"
        
        self.job_frame = ctk.CTkFrame(frame, bg_color="black", fg_color="black", height=30, border_color=border_color, border_width=border_width, corner_radius=corner_radius)
        self.job_frame.pack(fill="x", side="top", padx=5, pady=5, expand=True)
        self.job_frame.pack_propagate(False)
        mtg_sans_font= ctk.CTkFont(family='MTG Sans', size=15, weight='bold')
        self.job_name_label = ctk.CTkLabel(self.job_frame, text_color="white", font=mtg_sans_font, text=self.job_name, 
                                            corner_radius=corner_radius, fg_color="transparent", bg_color="transparent", height=20)
        self.job_name_label.pack(side="left", padx=5)
        
        self.job_status_label = ctk.CTkLabel(self.job_frame, text_color="white", font=mtg_sans_font, text="", height=20 ,
                                              corner_radius=corner_radius)
        self.job_status_label.pack(side="right", padx=5)
        
        self.set_job_status()
    
    def update_job_status(self, job_status):
        self.job_status = job_status
        self.set_job_status()
            
    def set_job_status(self):
        if self.job_status == 0:
            self.job_frame.configure(bg_color="black", fg_color="black")
            self.job_status_label.configure(text="In queue")
        
        elif self.job_status == 1:
            self.job_frame.configure(bg_color="#4D91DC", fg_color="#4D91DC")
            self.job_status_label.configure(text="In progress")
            
        elif self.job_status == 2:
            self.job_frame.configure(bg_color="#43C15F", fg_color="#43C15F")
            self.job_status_label.configure(text="Completed")
            
        else:
            self.job_frame.configure(bg_color="#F24E4D", fg_color="#F24E4D")
            self.job_status_label.configure(text="Failed - See output folder for details")
        
class label_image_button():
    
    #always needs 2 images, default state and highlighted. If 3 images are available, it is turned into a tab button, where the 3rd image is the currently active tab image.
    def __init__(self, frame, images, size, command, highlight=True):
        self.frame = frame
        self.size = size
        self.highlight=highlight
        self.def_image = ctk.CTkImage(light_image=Image.open(images[0]))
        self.def_image.configure(size=self.size)
        
        self.highlight_image = ctk.CTkImage(light_image=Image.open(images[1]))
        self.highlight_image.configure(size=self.size)
        
        if len(images) == 3:
            self.active_image = ctk.CTkImage(light_image=Image.open(images[2]))
            self.active_image.configure(size=self.size)
            
        self.command = command
    
        self.button = self.create_and_return_button()
    
    def configure_image(self, images):  
        self.def_image = ctk.CTkImage(light_image=Image.open(images[0]))
        self.def_image.configure(size=self.size)
        self.highlight_image = ctk.CTkImage(light_image=Image.open(images[1]))
        self.highlight_image.configure(size=self.size)
        
        self.button.configure(self.def_image)
        
    def get_button(self):
        return self.button

    def pack_button(self, side="left", anchor='center', pady=0, padx=0):
        self.button.pack(side=side, anchor=anchor, pady=pady, padx=padx)
    
    def grid_button(self, column=0, row=0, rowspan=1, columnspan=1, padx=0, pady=0):
        self.button.grid(column=column, row=row, rowspan=rowspan, columnspan=columnspan, padx=padx, pady=pady)

    def place_button(self, relx=0, rely=0, relwidth=None, relheight=None):
        self.button.place(relx=relx, rely=rely, relwidth=relwidth, relheight=relheight) 
        
    def create_and_return_button(self):
        button = ctk.CTkLabel(self.frame, image=self.def_image, text="")
        
        if self.highlight:
            button.bind("<Enter>", lambda e: self.on_button_enter(e))
            button.bind("<Leave>", lambda e: self.on_button_leave(e))
        button.bind("<Button-1>", lambda e: self.command())
        button.configure(cursor="hand2")
        return button
    
    def on_button_enter(self, e):
        self.button.configure(image = self.highlight_image)
        
    def on_button_leave(self, e):
        self.button.configure(image = self.def_image)
        
    def set_button_inactive(self):
        self.button.configure(image = self.def_image)
    
        self.button.bind("<Enter>", lambda e: self.on_button_enter(e))
        self.button.bind("<Leave>", lambda e: self.on_button_leave(e))
        self.button.bind("<Button-1>", lambda e: self.command())
        self.button.configure(cursor="hand2")
    
    def set_button_default(self):
        self.button.configure(image = self.def_image)
    
    def set_button_active(self):
        self.button.configure(image = self.active_image)
        
    def set_button_active_and_deactive(self):
        self.button.configure(image = self.active_image)
        self.button.configure(cursor="arrow")
        self.button.unbind("<Button-1>")
        self.button.unbind("<Enter>")
        self.button.unbind("<Leave>")

class jsonbase():
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(jsonbase, cls).__new__(cls)
            cls._instance.initialized = False 
        return cls._instance
    
    
    def update_job_status(entity_name, job_path, job_status):
        json_file = "media/jsonbase/entity_data.json"
        
        with open(json_file, 'r') as file:
            data = json.load(file)

        # Search for the entity by name
        for entity in data:
            if entity.get("name") == entity_name:
                # Search for the job with the matching job path
                for job in entity.get("jobs"):
                    if job.get("jobpath") == job_path:
                        job["jobstatus"] = job_status

        with open(json_file, 'w') as file:
            json.dump(data, file, indent=4)
        
    def initialize_entity_base():
        entity_path = "media/jsonbase/entity_data.json"

        directory = os.path.dirname(entity_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

        try:
            with open(entity_path, 'r') as file:
                data = json.load(file)
            print("JSON file already exists. No changes made.")
        except FileNotFoundError:
            data = []
            with open(entity_path, 'w') as file:
                json.dump(data, file, indent=4)
            print(f"JSON file '{entity_path}' created and initialized.")


    def remove_job(self, job_path):
        entity_path = "media/jsonbase/entity_data.json"

        with open(entity_path, 'r') as file:
            data = json.load(file)
            
        for entity in data:
            jobs = entity.get("jobs", [])
            job_to_remove = None

            for job in jobs:
                if job["jobpath"] == job_path:
                    job_to_remove = job
                    break

            if job_to_remove:
                jobs.remove(job_to_remove)
                with open(entity_path, 'w') as file:
                    json.dump(data, file, indent=4)

                print(f"Job with path '{job_path}' removed from entity '{entity['name']}'")
                return

        print(f"Job with path '{job_path}' not found in any entity.")


            
    def add_job(self, entity_name, job_status, job_name, job_path):
        entity_path = "media/jsonbase/entity_data.json"
        
        with open(entity_path, 'r') as file:
            data = json.load(file)

        found_entity = None

        for entity in data:
            if entity["name"] == entity_name:
                found_entity = entity
                break

        if found_entity:
            
            job = {
                "jobstatus": job_status,
                "jobname": job_name,
                "jobpath": job_path
            }

            found_entity.setdefault("jobs", []).append(job)

            with open(entity_path, 'w') as file:
                json.dump(data, file, indent=4)

            print(f"Job added to entity '{entity_name}' with name '{job_name}'")
        else:
            print(f"Entity with name '{entity_name}' not found.")
            
    def get_job_status(self, job_path):
        
        entity_path = "media/jsonbase/entity_data.json"
       
        with open(entity_path, 'r') as file:
            data = json.load(file)

        for project in data:
            for job in project.get('jobs', []):
                if job['jobpath'] == job_path:
                    
                    return job['jobstatus']

        return None
    
    def add_entity(self, name, path, filetype, language, priority):
        entity_path = "media/jsonbase/entity_data.json"

        with open(entity_path, 'r') as file:
            data = json.load(file)

        next_id = 1
        if data:
            next_id = max(entity["id"] for entity in data) + 1

        new_entity = {
            "id": next_id,
            "name": name,
            "path": path,
            "filetype": filetype,
            "language": language,
            "priority": priority,
            "jobs": []
        }

        data.append(new_entity)

        with open(entity_path, 'w') as file:
            json.dump(data, file, indent=4)

        print(f"Entity added with ID: {next_id}")
    
    
    def get_job_objects(self,entity, entity_data):
        
        jobs = entity_data.get("jobs", [])
        job_paths = {}
        for job_data in jobs:
            job_status = job_data['jobstatus']
            if job_status == 1:
                job_status = 0
            job_paths[job_data['jobpath']] = job_status
            entity.watchfolder_jobs.append_job(job_status, job_data['jobname'], job_data['jobpath'])
        entity.watcher.set_checked_directories(job_paths)
            
    def get_entity_objects(self, parent):
        entity_path = "media/jsonbase/entity_data.json"

        try:
            with open(entity_path, 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"JSON file '{entity_path}' does not exist.")
            return []

        entity_objects = []
        for entity_data in data:
            entity = watchfolder_entity(
                parent,
                entity_data["name"],
                entity_data["path"],
                entity_data["filetype"],
                entity_data["language"],
                entity_data["priority"],
            )

            self.get_job_objects(entity,entity_data)
        
            entity_objects.append(entity)

        return entity_objects

class labeled_progress_bar(ctk.CTkProgressBar):
    def __init__(self, currentvar, filevar, progressint, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.currentvar = currentvar
        self.filevar = filevar
        self.progressint = progressint

        # create the text item in the internal canvas
        self._canvas.create_text(0, 0, text=self.currentvar.get(), fill="white",
                                 font=('MTG Sans', 20), anchor="w", tags="current_text")
        
        self._canvas.create_text(0, 0, text=self.filevar.get(), fill="white",
                                 font=('MTG Sans', 20), anchor="e", tags="file")

        self._canvas.create_text(0, 0, text=self.progressint, fill="white",
                                 font=('MTG Sans', 20), anchor="c", tags="progress")

    def _update_dimensions_event(self, event):
        super()._update_dimensions_event(event)
        outerpadx=10
        
        self._canvas.coords("current_text", event.width-event.width+outerpadx, event.height/2)
        self._canvas.coords("file", event.width-outerpadx, event.height/2)
        self._canvas.coords("progress", event.width/2, event.height/2)

    def getprogress(self):
        return self.progressint
    
    def setcurrent(self, newtext):
        if len(newtext) > 13:
            shortened_string = newtext[:15] + "..."
            self.currentvar.set(shortened_string)
            self._canvas.itemconfigure("current_text", text=self.currentvar.get())
        else:
            self.currentvar.set(newtext)
            self._canvas.itemconfigure("current_text", text=self.currentvar.get())
        
    def setfile(self, newtext):
        self.filevar.set(newtext)
        self._canvas.itemconfigure("file", text=self.filevar.get())
        
    def setprogress_noadd(self, newint):
        self.progressint = newint
        self.set(self.progressint)
        self._canvas.itemconfigure("progress", text=str(int(self.progressint*100)) +"%") 
        
    def setprogress(self, newint):
        newint = self.progressint + newint
        self.progressint = newint
        self.set(self.progressint)
        self._canvas.itemconfigure("progress", text=str(int(self.progressint*100)) +"%") 
        
        
class watcher_local:


    
    def __init__(self):
        self.sync_files = []
        self.temp_sync_files = []
        self.reportage_files = []
        self.temp_reportage_files = []

        self.last_timestamps = {}
        self.lock = threading.Lock()
        try:
            jsonbase.initialize_entity_base()
            self.build_start_page()
        except Exception as e:
            with open("crash_dump.txt", "a") as dump_file:
                dump_file.write(e + "\n") 
        

    def check_license_key(self, license_key, result_callback):
        # try:
        #     # Connect to your MySQL database (replace with your database details)
        #     conn = mysql.connector.connect(
        #         host="",
        #         user="",
        #         password="",
        #         database=""
        #     )

        #     # Create a cursor
        #     cursor = conn.cursor()
        #     license_key = license_key.replace(' ', '')
        #     # Define the stored procedure call with the license key as an input parameter
        #     cursor.callproc("GetIsValidForLicenseKey", args=(license_key,))
        #     for result in cursor.stored_results():
        #         isActive = (result.fetchone())
            
            
        #     if isActive[0] != 0:
        #         isActive = True  # Extract the value
        #     else:
        #         isActive = False

        #     # Close the cursor and connection
        #     cursor.close()
        #     conn.close()

        #     # Callback with the isValidValue
        #     result_callback(isActive)
        # except mysql.connector.Error as e:
        #     print(f"MySQL Error: {e}")
        #     # Callback to handle errors
        #     result_callback(False)
        # except Exception as e:
        #     print(f"Error: {e}")
        #     # Callback to handle errors
        #     result_callback(False)
        result_callback(True)
    # Function to perform an action with the selected folder path
    # def activate(self):
        # self.select_button.configure(state=tk.DISABLED)
        # self.activate_button.configure(state=tk.DISABLED)
        # watchpath = self.folder_path_var.get()
        # self.stop_button.configure(state=tk.NORMAL)  # Enable the Stop button

        # # Start the main method in a separate thread
        # main_thread = threading.Thread(target=self.main, args=(watchpath,))
        # main_thread.daemon = True  # Allow the thread to be terminated with the GUI
        # main_thread.start()
        
    # Function to handle the result of the license check
    
    def handle_license_result(self, valid):
        # Re-enable the "Activate" button
        self.activate_license_button.configure(state=ctk.NORMAL)
        
        if valid:
            self.build_open_page()
            self.show_main_page()
        else:
            self.error_label.configure(text="Not a valid key/key not enabled/check internet connection or settings")


    def activate_license(self):
        license_key = self.license_entry.get()
        self.activate_license_button.configure(state=ctk.DISABLED)
        threading.Thread(target=lambda: self.check_license_key(license_key, self.handle_license_result)).start()
        
    def on_back_frame_configure(self, event, frame, image):
        frame.update()
        back_width = frame.winfo_width()
        back_height = frame.winfo_height()
        image.configure(size=(back_width,back_height))
    

        
    def show_main_page(self):
        
        #---------header-------------
        self.header_frame.pack(side = 'top', fill='x', anchor='n')
        self.header_frame.pack_propagate(False)
        
        
        self.page_buttons_frame.pack(side='left', anchor='sw')
        
        self.active_jobs_button.pack_button(side='left', padx=10)
        
        self.cur_active_frame = None
        self.cur_active_button = None
    
        self.show_main_page_active_jobs()
        
        self.watchfolders_button.pack_button(side='left', padx=10)
        self.settings_button.pack_button(side='left', padx=10)
        
        self.header_pro_logo_frame.pack(side='right', anchor='e', fill='y', expand=True,padx=10)
        self.header_pro_image_label.pack(pady=15)
        
        #---------header-------------
        
        #---------footer-------------
        self.footer_frame.pack(side='bottom', fill='x')
        self.footer_frame.pack_propagate(False)
        self.footer_frame.configure(fg_color='#404A56', bg_color='#404A56')

        self.footer_version_frame.pack(side='left', anchor='sw', padx=10)
        self.footer_version_label.pack(side='left', anchor='sw')
        
        self.footer_buttons_frame.pack(side='right', anchor='e', padx=10)
        self.footer_close_button.pack_button(side='top', anchor='n', pady=5)
        self.footer_exit_button.pack_button(side='bottom', anchor='s')
        
        
        #---------footer-------------
        
        #---------body----------------
        self.body_frame.pack(fill="both", expand=True)
        
        #---------body----------------
        
        # Forget the License Page widgets
        self.license_frame.pack_forget()
    #----
    def show_main_page_active_jobs(self):
        self.active_jobs_button.set_button_active_and_deactive()
        if self.cur_active_frame != None and self.cur_active_button != None:
            self.cur_active_button.set_button_inactive()
            self.cur_active_frame.pack_forget()
        self.cur_active_button = self.active_jobs_button
        self.cur_active_frame = self.active_jobs_frame
        
        
        
        self.active_jobs_frame.pack(fill='both', expand=True)
        


    def job_activity(self):
        while True:
            queued_jobs = 0
            completed_jobs = 0
            
            entity_container = self.watchfolderentity_list
            
            for entity in entity_container.entity_list:
                internal_queued_jobs = 0
                internal_completed_jobs = 0
                for path, job in entity.get_job_dict().items():
                        
                    if job.job_status == 0 or job.job_status == 1:
                        queued_jobs += 1
                        internal_queued_jobs += 1
                        
                    if job.job_status == 2:
                        completed_jobs += 1
                        internal_completed_jobs += 1
                        
                entity.entity_info_queued_var.set(str(internal_queued_jobs))
                entity.entity_info_completed_var.set(str(internal_completed_jobs))   
                     
            self.job_summary_completed_var.set(str(completed_jobs))
            self.job_summary_queued_var.set(str(queued_jobs))
            
                
            
            time.sleep(10)
    
    def get_computer_name(self):
        
        computer_name = socket.gethostname()
        return computer_name
    
    def build_main_page_active_jobs(self):
        self.active_jobs_frame = ctk.CTkLabel(self.body_frame, bg_color='#DCD7D7', image=self.back_image, text="")
        self.active_jobs_frame.bind("<Configure>", lambda event: self.on_back_frame_configure(event, self.active_jobs_frame, self.back_image))
        #job summary
        self.job_summary_frame = ctk.CTkFrame(self.active_jobs_frame, bg_color='#DCD7D7')
        self.job_summary_frame.place(relx=0.15, rely=0.152)
        
        self.job_summary_label_image = ctk.CTkImage(light_image=Image.open("Media/Job summary.png"), size=(400, 187))
        self.job_summary_label = ctk.CTkLabel(self.job_summary_frame, bg_color="#DCD7D7", image=self.job_summary_label_image, text="")
        self.job_summary_label.pack()
        
        self.job_summary_completed_var = tk.StringVar()
        self.job_summary_completed_var.set("0")
        self.job_summary_completed_label = ctk.CTkLabel(self.job_summary_label, textvariable=self.job_summary_completed_var, font=self.mtg_sans_font, bg_color="#6D6B6B", fg_color="#6D6B6B", text_color="#58FF79")
        self.job_summary_completed_label.place(rely=0.65, relx = 0.75)
        
        self.job_summary_queued_var = tk.StringVar()
        self.job_summary_queued_var.set("0")
        self.job_summary_queued_label = ctk.CTkLabel(self.job_summary_label, textvariable=self.job_summary_queued_var, font=self.mtg_sans_font, bg_color="#6D6B6B", fg_color="#6D6B6B", text_color="#FF9C00")
        self.job_summary_queued_label.place(rely=0.48, relx = 0.75)
        #job summary
        
        #prologue engine
        self.prologue_engine_frame = ctk.CTkFrame(self.active_jobs_frame, bg_color='#DCD7D7')
        self.prologue_engine_frame.place(relx=0.45, rely=0.1)
        self.prologue_engine_label_image = ctk.CTkImage(light_image=Image.open("Media/Prologue Engine.png"), size=(700, 228))
        self.prologue_engine_label = ctk.CTkLabel(self.prologue_engine_frame, image=self.prologue_engine_label_image, text="", bg_color="#DCD7D7")
        self.prologue_engine_label.pack()
        
        currentjob_font = ctk.CTkFont(family='MTG Sans', size=20, weight='normal')
        
        self.prologue_id = self.get_computer_name()
        self.prologue_id_label = ctk.CTkLabel(self.prologue_engine_label, text=self.prologue_id, font=self.mtg_sans_bold_font, bg_color="#6D6B6B", fg_color="#6D6B6B", text_color="#FFFFFF")
        self.prologue_id_label.place(rely=0.31, relx = 0.48)
        
        self.prologue_engine_currentjob_frame = ctk.CTkFrame(self.prologue_engine_label, bg_color="#6D6B6B", fg_color="#6D6B6B",)
        self.prologue_engine_currentjob_frame.place(rely=0.65, relx = 0.05, relwidth = 0.9, relheight=0.3)
        
        self.prologue_engine_currentjob_var = tk.StringVar()
        self.prologue_engine_currentjob_files_var = tk.StringVar()
        self.prologue_engine_progress_int = 0.0
        self.prologue_engine_progressbar = labeled_progress_bar(self.prologue_engine_currentjob_var, self.prologue_engine_currentjob_files_var,  self.prologue_engine_progress_int, master=self.prologue_engine_currentjob_frame, height = 300)
        self.prologue_engine_progressbar.setprogress_noadd(0)
        self.prologue_engine_currentjob_work_var=tk.StringVar()
        self.prologue_engine_currentjob_work_var.set("")
        self.prologue_engine_currentjob_work_label = ctk.CTkLabel(self.prologue_engine_currentjob_frame, textvariable=self.prologue_engine_currentjob_work_var, font=currentjob_font, bg_color="#6D6B6B", fg_color="#6D6B6B", text_color="#FFFFFF")
        self.prologue_engine_currentjob_work_label.pack()
        self.prologue_engine_progressbar.pack(fill="x")
        
        # self.prologue_queue_frame = ctk.CTkFrame(self.active_jobs_frame, bg_color='transparent')
        # self.prologue_queue_frame.place(relx=0.07, rely=0.5)
        # self.prologue_queue_label_image = ctk.CTkImage(light_image=Image.open("Media/Job Queue - Job area + baggrund.png"), size=(717, 377))
        # self.prologue_queue_label = ctk.CTkLabel(self.prologue_queue_frame, image=self.prologue_queue_label_image, text="", bg_color="#DCD7D7")
        # self.prologue_queue_label.pack()
        
        # self.prologue_queue_text_label_image = ctk.CTkImage(light_image=Image.open("Media/Job Queue tekst.png"), size=(386, 89))
        # self.prologue_queue_text_label = ctk.CTkLabel(self.prologue_queue_label, image=self.prologue_queue_text_label_image, text="", bg_color='#6D6B6B')
        # self.prologue_queue_text_label.place(relx=0.23, rely=0.05)
        
        #prologue engine
    #-----    
    #-----
    def show_main_page_watchfolders(self):
        self.watchfolders_button.set_button_active_and_deactive()
        self.cur_active_button.set_button_inactive()
        self.cur_active_frame.pack_forget()
        self.cur_active_button = self.watchfolders_button
        self.cur_active_frame = self.watchfolders_frame
        
        self.watchfolders_frame.pack(fill='both', expand=True)

    def build_main_page_watchfolders(self):
        self.watchfolders_frame = ctk.CTkLabel(self.body_frame, bg_color='#DCD7D7', image=self.back_image, text="")
        self.watchfolders_frame.bind("<Configure>", lambda event: self.on_back_frame_configure(event, self.watchfolders_frame, self.back_image))
        
        #right frame/creation-edit window
        self.watchfolder_settings_back_frame = ctk.CTkFrame(self.watchfolders_frame, bg_color="#82817F", fg_color="#82817F")
        self.watchfolder_settings_back_frame.place(relx=0.70, rely=0.02, relwidth=0.29, relheight=0.955)
        
        settings_background_image = ctk.CTkImage(light_image=Image.open("media/CHOOSE TO ACTIVATE.png"), size=(500,100))
        self.watchfolder_empty_settings_background = ctk.CTkLabel(self.watchfolder_settings_back_frame, image=settings_background_image, text="", 
                                                                  bg_color="transparent", fg_color="transparent")
        self.watchfolder_empty_settings_background.pack(fill='both', expand=True)

        self.watchfolder_settings_new_button = label_image_button(self.watchfolder_empty_settings_background,
                                                                  images=("media/New Watchfolder.png",
                                                                  "media/New Watchfolder.png"),
                                                                  size=(172,50),
                                                                  command=lambda: self.build_createnew_settings(self.watchfolder_settings_back_frame))
        
        self.watchfolder_settings_new_button.place_button(relx=0.02, rely=0.92)
        #right frame/creation-edit window
        
        #left frame/watchfolderlist
        self.watchfolderlist_frame = ctk.CTkScrollableFrame(self.watchfolders_frame, bg_color="#DCD6D6", fg_color="#DCD6D6")
        self.watchfolderlist_frame.place(relx=0.01, rely=0.02, relwidth=0.66, relheight=0.955)
        
        self.watchfolderentity_list = watchfolder_entity_container(self.watchfolderlist_frame)
        #left frame/watchfolders
    def set_column_widths(self, frame, num_columns):
        for column in range(num_columns):
            frame.grid_columnconfigure(column, weight=1)
    
    def select_folder(self, variable):
        folder_path = filedialog.askdirectory()
        
        if folder_path:
            variable.set(folder_path)
        
        else: 
            variable.set("Select watchfolder path")
    
    #TODO alt der har med  aaf, fcpxml, ppxml, txt, srt (checkboxes) at gøre skal ændres og gøres bedre... det noget skrammel det der
    def create_watchfolder(self, name, path, aaf, fcpxml, ppxml, txt, srt, language, priority, 
                           namedef, pathdef, filetypedef, languagedef, prioritydef,
                           errorlabel, frame):       

        error = False
        
        if name.get() == namedef:
            errorlabel.configure(text="Enter a project name")
            error = True
            
        elif path.get() == pathdef:
            errorlabel.configure(text="Choose a watchfolder path")
            error = True
            
        elif not os.path.isdir(path.get()):
            errorlabel.configure(text="Chosen path does not exist")
            error = True
            
        elif aaf.get() == filetypedef and fcpxml.get() == filetypedef and ppxml.get() == filetypedef:
            errorlabel.configure(text="Must choose at least one filetype")
            error = True
            
        elif language.get() == languagedef:
            errorlabel.configure(text="Choose a language")
            error = True
        
        elif priority.get() == prioritydef:
            errorlabel.configure(text="Choose a priority")
            error = True
            
        container = watchfolder_entity_container()
        for entity in container.entity_list:
            if entity.path == path.get():
                errorlabel.configure(text="A watcher on that path already exists")
                error = True
                break
            elif entity.name.lower() == name.get().lower():
                errorlabel.configure(text="A project with that name already exists")
                error = True
                break
        
        filetypes = {"aaf": aaf.get(), "fcpxml": fcpxml.get(), "ppxml":ppxml.get(), "txt":txt.get(), "srt":srt.get()}
        
        if not error:
            self.watchfolder_empty_settings_background.pack(fill='both', expand=True)
            frame.forget()
            self.watchfolderentity_list.append_entity(name.get(), path.get(), filetypes, language.get(), priority.get())
    

        
        
    def build_createnew_settings(self, frame):
        self.watchfolder_empty_settings_background.forget()
        padx=50
        pady=15
        label_pady=15
        
        create_new_frame = ctk.CTkFrame(frame, bg_color="transparent", fg_color="transparent")
        
        project_name_var_def = ""
        project_name_var = tk.StringVar()
        project_name_var.set(project_name_var_def)
        project_name_frame = ctk.CTkFrame(create_new_frame, bg_color="transparent", fg_color="transparent")
        project_name_frame.pack(fill="x", pady=pady)
        project_name_label = ctk.CTkLabel(project_name_frame, font=self.mtg_sans_bold_font, text="PROJECT NAME:")
        project_name_label.pack(fill="x", padx=padx, pady=label_pady)
        project_name_entry = ctk.CTkEntry(project_name_frame, height=35, textvariable=project_name_var)
        project_name_entry.pack(fill="x", padx=padx)
        
        folder_path_var_def = "Select watchfolder path"
        folder_path_var = tk.StringVar()
        folder_path_var.set(folder_path_var_def)
        project_path_frame = ctk.CTkFrame(create_new_frame, bg_color="transparent", fg_color="transparent")
        project_path_frame.pack(fill="x", pady=pady)
        project_path_label = ctk.CTkLabel(project_path_frame, font=self.mtg_sans_bold_font, text="CHOOSE PROJECT PATH:")
        project_path_label.pack(fill="x", padx=padx, pady=label_pady)
        project_path_button = ctk.CTkButton(project_path_frame, text="Choose path", height=35, command= lambda: self.select_folder(folder_path_var))
        project_path_button.pack(side="left", padx=(50,20))
        project_path_entry = ctk.CTkEntry(project_path_frame, textvariable=folder_path_var, state="disabled", width=290)
        project_path_entry.pack(side="left", fill="x")
        

            
        project_filetype_var_def = "off"
        project_aaf_var = tk.StringVar()
        project_aaf_var.set(project_filetype_var_def)
        project_fcpxml_var = tk.StringVar()
        project_fcpxml_var.set(project_filetype_var_def)
        project_ppxml_var = tk.StringVar()
        project_ppxml_var.set(project_filetype_var_def)
        project_txt_var = tk.StringVar()
        project_txt_var.set(project_filetype_var_def)
        project_srt_var = tk.StringVar()
        project_srt_var.set(project_filetype_var_def)
        
        project_filetype_frame = ctk.CTkFrame(create_new_frame, bg_color="transparent", fg_color="transparent")
        project_filetype_frame.pack(fill="x", pady=pady)
        project_filetype_label = ctk.CTkLabel(project_filetype_frame, font=self.mtg_sans_bold_font, text="CHOOSE FILETYPE:")
        project_filetype_label.grid(row=0, column=0, columnspan=3, pady=label_pady)
        
        project_aaf_checkbox = ctk.CTkCheckBox(project_filetype_frame, text="Avid AAF",
                                         variable=project_aaf_var, onvalue="on", offvalue="off",)
        project_aaf_checkbox.grid(row=1, column=0, padx=padx, pady=label_pady, sticky="w")
        
        project_fcpxml_checkbox = ctk.CTkCheckBox(project_filetype_frame, text="Final Cut XML",
                                         variable=project_fcpxml_var, onvalue="on", offvalue="off", state=tk.DISABLED, text_color_disabled="white")
        project_fcpxml_checkbox.grid(row=1, column=1, pady=label_pady, sticky="w")
        
        project_ppxml_checkbox = ctk.CTkCheckBox(project_filetype_frame, text="Premiere Pro XML",
                                         variable=project_ppxml_var, onvalue="on", offvalue="off", state=tk.DISABLED, text_color_disabled="white")
        project_ppxml_checkbox.grid(row=1, column=2, pady=label_pady, sticky="w")
        
        project_txt_checkbox = ctk.CTkCheckBox(project_filetype_frame, text="Text document",
                                         variable=project_txt_var, onvalue="on", offvalue="off")
        project_txt_checkbox.grid(row=2, column=0,  padx=padx, pady=label_pady, sticky="w")
        
        project_srt_checkbox = ctk.CTkCheckBox(project_filetype_frame, text="Subtitle file (.SRT)",
                                         variable=project_srt_var, onvalue="on", offvalue="off")
        project_srt_checkbox.grid(row=2, column=1, pady=label_pady, sticky="w")
        
        project_languages = ["Armenian", "Croatian", "Czech", "Danish", "Dutch", "English", "Estonian", "Finnish", "German", "Norwegian", "Swedish"]
        project_language_var_def = "Choose Language"
        project_language_var = tk.StringVar()
        project_language_var.set(project_language_var_def)
        project_language_frame = ctk.CTkFrame(create_new_frame, bg_color="transparent", fg_color="transparent")
        project_language_frame.pack(fill="x", pady=pady, padx=padx)
        project_language_label = ctk.CTkLabel(project_language_frame, font=self.mtg_sans_bold_font, text="CHOOSE LANGUAGE:")
        project_language_label.pack(fill="x", padx=padx, pady=label_pady)
        project_language_optionmenu = ctk.CTkOptionMenu(project_language_frame, values=project_languages,
                                         variable=project_language_var)
        project_language_optionmenu.pack(fill="x", padx=padx)
        
        
        project_prio_var_def = "Choose folder priority"
        project_prio_var = tk.StringVar()
        project_prio_var.set(project_prio_var_def)
        project_prio_frame = ctk.CTkFrame(create_new_frame, bg_color="transparent", fg_color="transparent")
        project_prio_frame.pack(fill="x", padx=padx)
        project_prio_label = ctk.CTkLabel(project_prio_frame, font=self.mtg_sans_bold_font, text="CHOOSE PRIORITY:")
        project_prio_label.pack(fill="x", padx=padx, pady=label_pady)
        project_prio_optionmenu = ctk.CTkOptionMenu(project_prio_frame, values=["LOW", "MEDIUM", "HIGH"],
                                         variable=project_prio_var)
        project_prio_optionmenu.pack(fill="x", padx=padx)

        project_create_frame = ctk.CTkFrame(create_new_frame, bg_color="transparent", fg_color="transparent")
        project_create_frame.pack(fill="x", padx=padx)
        project_create_error_label = ctk.CTkLabel(project_create_frame, fg_color="transparent", bg_color="transparent", text_color="red",
                                                  text="")  
        project_create_error_label.pack(padx=padx, pady=(20,0))
        project_create_button = ctk.CTkButton(project_create_frame, text="Create Watchfolder", height=35, command=
                                              lambda: self.create_watchfolder(project_name_var, folder_path_var, project_aaf_var, project_fcpxml_var, project_ppxml_var, project_txt_var, project_srt_var, project_language_var, project_prio_var,
                                                                              project_name_var_def, folder_path_var_def, project_filetype_var_def, project_language_var_def, project_prio_var_def,
                                                                              project_create_error_label, create_new_frame))
        project_create_button.pack(padx=padx)
        
        create_new_frame.pack(fill="both", expand=True)
        
    #-----    
    #-----       
    def show_main_page_settings(self):
        self.settings_button.set_button_active_and_deactive()
        self.cur_active_button.set_button_inactive()
        self.cur_active_frame.pack_forget()
        self.cur_active_button = self.settings_button
        self.cur_active_frame = self.settings_frame
        
        self.settings_frame.pack(fill='both', expand=True)
        self.slabel.pack()
        
    def build_main_page_settings(self):
        self.settings_frame = ctk.CTkFrame(self.body_frame, fg_color='transparent')
        self.settings_frame.bind("<Configure>", lambda event: self.on_back_frame_configure(event, self.settings_frame, self.back_image))
        self.slabel = ctk.CTkLabel(self.settings_frame, anchor='center', text="SETTINGS")
    #---    
    
    def build_open_page(self):
        
        #---------header-------------
        self.header_frame = ctk.CTkFrame(self.root, height=100, corner_radius=0, fg_color='#404A56', bg_color='#404A56')
        self.page_buttons_frame = ctk.CTkFrame(self.header_frame, fg_color='transparent')
        self.header_pro_logo_frame = ctk.CTkFrame(self.header_frame, fg_color='transparent')
        
        self.mtg_sans_bold_font= ctk.CTkFont(family='MTG Sans', size=30, weight='bold')
        self.mtg_sans_font= ctk.CTkFont(family='MTG Sans', size=30, weight='normal')
        
        page_button_size=(229,50)
        
        self.active_jobs_button = label_image_button(
                                  frame=self.page_buttons_frame,
                                  images=("media/Active Jobs not active.png",
                                          "media/Active Jobs highlighted.png",
                                          "media/Active Jobs active.png"),
                                  size=page_button_size,
                                  command=self.show_main_page_active_jobs
                                  )
        self.watchfolders_button = label_image_button(
                                  frame=self.page_buttons_frame,
                                  images=("media/Watchfolder not active.png",
                                          "media/Watchfolder highlighted.png",
                                          "media/Watchfolder active.png"),
                                  size=page_button_size,
                                  command=self.show_main_page_watchfolders
                                  )
        
        self.settings_button = label_image_button(
                            frame=self.page_buttons_frame,
                            images=("media/Settings not active.png",
                                    "media/Settings highlighted.png",
                                    "media/Settings active.png"),
                            size=page_button_size,
                            command=self.show_main_page_settings
                            )
        
        self.header_pro_image = ctk.CTkImage(light_image=Image.open("media/Prologue logo - hvidt.png"), size=(188, 60))
        
        self.header_pro_image_label = ctk.CTkLabel(self.header_pro_logo_frame, text='', image=self.header_pro_image)
        #---------header-------------
        
        #---------body-------------
        self.back_image = ctk.CTkImage(light_image=Image.open("media/Mainpage - Background.png"))
        self.body_frame = ctk.CTkFrame(self.root, corner_radius=0)
        

        #---------build button pages---------
        self.build_main_page_watchfolders()
        self.build_main_page_active_jobs()
        self.build_main_page_settings()
        job_activity_thread = threading.Thread(target=self.job_activity)
        job_activity_thread.daemon = True

        job_activity_thread.start()
        #---------build button pages---------
        
        #---------body-------------
        
        #---------footer-------------
        self.footer_frame = ctk.CTkFrame(self.root, height = 90, corner_radius=0)
        
        self.footer_version_frame = ctk.CTkFrame(self.footer_frame, corner_radius=0, fg_color="transparent")
        self.footer_version_label = ctk.CTkLabel(self.footer_version_frame, font=self.mtg_sans_font, text='V 1.0.0')
        
        self.footer_buttons_frame = ctk.CTkFrame(self.footer_frame, corner_radius=0, fg_color='transparent')
        
        self.footer_exit_button = label_image_button(
                                  frame=self.footer_buttons_frame,
                                  images=("media/Exit and close not active.png",
                                          "media/Exit and close highlighted.png"),
                                  size=(140,28),
                                  command=lambda: print(1)
                                  )
        self.footer_close_button = label_image_button(
                                    frame=self.footer_buttons_frame,
                                    images=("media/Close Prologue not active.png",
                                          "media/Close Prologue highlighted.png"),
                                    size=(140,28),
                                    command=lambda: print(1)
                                    )
        

        
        #---------footer-------------
        #---------start transscriber-----
        whisper_transscriber(watchfolder_entity_container(), self.prologue_engine_progressbar, self.prologue_engine_currentjob_work_var)
        
    
    def build_start_page(self):
        # Create the main window
        self.root = tk.Tk()
        self.root.title("Prologue")
        self.root.iconbitmap('media/PL Icon.ico')
        

        #---licenspage----
        # Create a frame for the License Page
        self.license_frame = ctk.CTkFrame(self.root)
        self.license_frame.pack()


        # Create a label for your logo on the License Page
        self.logo = ctk.CTkImage(light_image=Image.open("media/Prologue.png"),
                                  dark_image=Image.open("media/Prologue.png"), 
                                  size=(500,281))
        
        self.logo_label = ctk.CTkLabel(self.license_frame, image=self.logo, text='')
        self.logo_label.pack()
        
        # Create an entry field for the license key
        self.license_label = ctk.CTkLabel(self.license_frame, text="Enter License Key:")
        self.license_label.pack()
        
        self.license_entry = ctk.CTkEntry(self.license_frame)
        self.license_entry.pack()

        # Create a button to activate the license key
        self.activate_license_button = ctk.CTkButton(self.license_frame, text="Activate", command=self.activate_license)
        self.activate_license_button.pack()
        
        # Create a label for displaying error messages on the License Page
        self.error_label = ctk.CTkLabel(self.license_frame, text="", text_color="red")
        self.error_label.pack()
        #---licenspage----

        
        

        self.root.state("zoomed")
        self.root.mainloop()

    
if __name__ == "__main__":
    watcher_local()
    
    
    

    
     