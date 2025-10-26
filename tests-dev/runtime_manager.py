import os
import sys
import signal
import subprocess

class RuntimeManager:
    def __init__(self, lockdir, rocoto=False, ecflow=False):
        self.lockdir = lockdir
        self.pid_file = os.path.join(lockdir, "PID")
        self.rocoto = rocoto
        self.ecflow = ecflow
        self.setup_lock()
        self.setup_traps()

    def setup_lock(self):
        try:
            os.mkdir(self.lockdir)
            with open(self.pid_file, "w") as f:
                f.write(f"{os.uname().nodename} {os.getpid()}\n")
            print(f"[INFO] Lock acquired: {self.lockdir}")
        except FileExistsError:
            print("[ERROR] Another instance is already running.")
            sys.exit(1)

    def setup_traps(self):
        signal.signal(signal.SIGINT, self.rt_trap)
        signal.signal(signal.SIGTERM, self.rt_trap)
        signal.signal(signal.SIGQUIT, self.rt_trap)
        sys.excepthook = self.handle_exception

    def rt_trap(self, signum, frame):
        print(f"[INFO] Received signal {signum}. Cleaning up...")
        if self.rocoto:
            self.rocoto_kill()
        if self.ecflow:
            self.ecflow_kill()
        self.cleanup()

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        print(f"[ERROR] Uncaught exception: {exc_value}")
        self.cleanup()

    def cleanup(self):
        try:
            if os.path.exists(self.pid_file):
                with open(self.pid_file) as f:
                    pid = f.read().split()[1]
                if pid == str(os.getpid()):
                    os.remove(self.pid_file)
                    os.rmdir(self.lockdir)
                    print(f"[INFO] Lock released: {self.lockdir}")
        except Exception as e:
            print(f"[WARN] Cleanup failed: {e}")
        if self.ecflow:
            self.ecflow_stop()
        sys.exit(0)

    def rocoto_kill(self):
        print("[INFO] Rocoto kill requested (stub)")

    def ecflow_kill(self):
        print("[INFO] ecFlow kill requested (stub)")

    def ecflow_stop(self):
        print("[INFO] ecFlow stop requested (stub)")

    def run_subprocess(self, cmd, check=True, capture_output=False, text=True):
        try:
            print(f"[INFO] Running subprocess: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=check, capture_output=capture_output, text=text)
            return result
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Subprocess failed: {e}")
            self.cleanup()
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            self.cleanup()
