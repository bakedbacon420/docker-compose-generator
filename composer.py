import tkinter as tk
from tkinter import scrolledtext, messagebox
import re
import yaml
import pyperclip

class DockerRunToComposeConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Docker Run to Compose Converter")
        self.root.geometry("800x600")
        
        # Input frame
        input_frame = tk.Frame(root)
        input_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(input_frame, text="Enter docker run command:").pack(anchor="w")
        
        self.input_text = scrolledtext.ScrolledText(input_frame, height=10)
        self.input_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Example button
        example_btn = tk.Button(input_frame, text="Load Example", command=self.load_example)
        example_btn.pack(pady=5)
        
        # Convert button
        convert_btn = tk.Button(input_frame, text="Convert to docker-compose", command=self.convert)
        convert_btn.pack(pady=5)
        
        # Output frame
        output_frame = tk.Frame(root)
        output_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(output_frame, text="docker-compose.yml output:").pack(anchor="w")
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=15)
        self.output_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Copy button
        copy_btn = tk.Button(output_frame, text="Copy to Clipboard", command=self.copy_to_clipboard)
        copy_btn.pack(pady=5)
    
    def load_example(self):
        example = '''$ docker run -d \\
    --name lodestone \\
    --restart unless-stopped \\
    -p 16662:16662 \\
    -v lodestone:/home/user/.lodestone \\
    ghcr.io/lodestone-team/lodestone_core'''
        self.input_text.delete(1.0, tk.END)
        self.input_text.insert(tk.END, example)
    
    def copy_to_clipboard(self):
        output = self.output_text.get(1.0, tk.END)
        pyperclip.copy(output)
        messagebox.showinfo("Copied", "Docker Compose YAML has been copied to clipboard")
    
    def convert(self):
        docker_run_cmd = self.input_text.get(1.0, tk.END).strip()
        
        # Clean up the command - remove $ and backslashes
        docker_run_cmd = docker_run_cmd.replace('$', '').replace('\\', '').strip()
        
        # Check if it's a docker run command
        if not docker_run_cmd.startswith('docker run'):
            messagebox.showerror("Error", "This doesn't appear to be a docker run command")
            return
        
        # Parse the command
        try:
            compose_yaml = self.parse_docker_run(docker_run_cmd)
            yaml_str = yaml.dump(compose_yaml, sort_keys=False)
            
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, yaml_str)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse command: {str(e)}")
    
    def parse_docker_run(self, docker_run_cmd):
        # Split command by spaces but preserve quoted values
        parts = []
        current = ''
        in_quotes = False
        quote_char = None
        
        for char in docker_run_cmd:
            if char in ['"', "'"]:
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current += char
            elif char.isspace() and not in_quotes:
                if current:
                    parts.append(current)
                    current = ''
            else:
                current += char
        
        if current:
            parts.append(current)
        
        # Remove "docker" and "run" from parts
        if len(parts) >= 2 and parts[0] == 'docker' and parts[1] == 'run':
            parts = parts[2:]
        
        # Initialize compose structure
        compose = {
            'version': '3',
            'services': {},
            'volumes': {}
        }
        
        service_name = None
        service_config = {
            'image': None,
            'container_name': None,
            'restart': None,
            'ports': [],
            'volumes': [],
            'environment': [],
            'networks': []
        }
        
        # Parse docker run arguments
        i = 0
        while i < len(parts):
            part = parts[i]
            
            # Handle image (last argument without flag)
            if i == len(parts) - 1 and not part.startswith('-'):
                service_config['image'] = part
                
                # If no name was provided, use the image name as service name
                if not service_name:
                    service_name = part.split('/')[-1].split(':')[0]
                
            # Handle named container
            elif part == '--name' and i + 1 < len(parts):
                service_name = parts[i + 1]
                service_config['container_name'] = parts[i + 1]
                i += 1
                
            # Handle restart policy
            elif part == '--restart' and i + 1 < len(parts):
                service_config['restart'] = parts[i + 1]
                i += 1
                
            # Handle port mapping
            elif (part == '-p' or part == '--publish') and i + 1 < len(parts):
                service_config['ports'].append(parts[i + 1])
                i += 1
                
            # Handle volume mapping
            elif (part == '-v' or part == '--volume') and i + 1 < len(parts):
                volume = parts[i + 1]
                service_config['volumes'].append(volume)
                
                # If this is a named volume, add it to volumes section
                if ':' in volume and not volume.startswith('/'):
                    volume_name = volume.split(':')[0]
                    # Check if it's not a relative path
                    if '/' not in volume_name and '.' not in volume_name:
                        compose['volumes'][volume_name] = {'external': False}
                
                i += 1
                
            # Handle environment variables
            elif (part == '-e' or part == '--env') and i + 1 < len(parts):
                service_config['environment'].append(parts[i + 1])
                i += 1
                
            # Handle network
            elif (part == '--network') and i + 1 < len(parts):
                service_config['networks'].append(parts[i + 1])
                i += 1
                
            # Handle detached mode (ignore)
            elif part == '-d' or part == '--detach':
                pass
                
            i += 1
        
        # Use image name as service name if none specified
        if not service_name and service_config['image']:
            service_name = service_config['image'].split('/')[-1].split(':')[0]
        
        # If we still don't have a service name, use a default
        if not service_name:
            service_name = 'app'
        
        # Clean up empty config options
        for key in list(service_config.keys()):
            if service_config[key] is None or (isinstance(service_config[key], list) and len(service_config[key]) == 0):
                del service_config[key]
        
        # Add service to compose
        compose['services'][service_name] = service_config
        
        # If no volumes were defined, remove volumes section
        if not compose['volumes']:
            del compose['volumes']
            
        return compose

if __name__ == "__main__":
    root = tk.Tk()
    app = DockerRunToComposeConverter(root)
    root.mainloop()
