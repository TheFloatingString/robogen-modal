import os
import sys
import subprocess

# Set UTF-8 encoding for Python
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Run modal
subprocess.run([sys.executable, '-m', 'modal', 'run', 'robogen_modal.py'])
