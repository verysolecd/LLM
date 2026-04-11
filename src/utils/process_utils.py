import subprocess
import platform

def kill_proc_tree(pid):
    """
    Kill a process tree starting from pid.
    """
    if platform.system() == "Windows":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], 
                           check=True, 
                           capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Error killing process tree {pid}: {e.stderr}")
    else:
        # Fallback for non-windows if needed
        import psutil
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.kill()
            parent.kill()
        except psutil.NoSuchProcess:
            pass
