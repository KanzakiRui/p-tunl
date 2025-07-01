import os
import sys
import time
import subprocess
import threading
import logging
from pathlib import Path
import gradio as gr
from modules import shared, script_callbacks

# Setup configuration
CACHE_DIR = Path('.cache/pinggy_tunnel')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = CACHE_DIR / 'pinggy.log'
OUTPUT_FILE = CACHE_DIR / 'output.txt'

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TunnelState:
    instance = None
    url = None
    process = None
    active = False
    port = None

def start_tunnel():
    if TunnelState.active:
        logging.warning("Tunnel is already active")
        return
        
    TunnelState.active = True
    port = TunnelState.port or shared.cmd_opts.port or 7860
    
    def run_tunnel():
        try:
            logging.info(f"Starting SSH tunnel for port {port}")
            # Clear previous output
            if OUTPUT_FILE.exists():
                OUTPUT_FILE.unlink()
                
            # Start tunnel process
            TunnelState.process = subprocess.Popen(
                [
                    'ssh', '-o', 'StrictHostKeyChecking=no', 
                    '-p', '80', '-R0:localhost:{}'.format(port),
                    'a.pinggy.io'
                ],
                stdout=open(OUTPUT_FILE, 'w'),
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Monitor for URL
            start_time = time.time()
            timeout = 30
            while time.time() - start_time < timeout:
                time.sleep(2)
                if not OUTPUT_FILE.exists():
                    continue
                    
                with open(OUTPUT_FILE, 'r') as f:
                    content = f.read()
                    if 'http:' in content and '.pinggy.link' in content:
                        start_idx = content.find('http:')
                        end_idx = content.find('.pinggy.link') + len('.pinggy.link')
                        TunnelState.url = content[start_idx:end_idx]
                        logging.info(f"Tunnel established: {TunnelState.url}")
                        return
            
            logging.warning("Timeout reached, URL not found")
        except Exception as e:
            logging.error(f"Tunnel error: {str(e)}")
            TunnelState.active = False

    # Start in background thread
    threading.Thread(target=run_tunnel, daemon=True).start()

def stop_tunnel():
    if TunnelState.process:
        try:
            TunnelState.process.terminate()
            logging.info("Tunnel stopped")
        except:
            pass
    TunnelState.active = False
    TunnelState.url = None
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()

def on_app_started(demo, app):
    # Check if tunnel should start automatically
    if getattr(shared.cmd_opts, 'pinggy_tunnel', False):
        start_tunnel()

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as ui:
        gr.Markdown("## Pinggy Tunnel")
        
        with gr.Row():
            status = gr.Textbox("Status: Inactive", label="Tunnel Status", interactive=False)
            url_display = gr.Textbox("No active tunnel", label="Public URL", interactive=False)
        
        with gr.Row():
            start_btn = gr.Button("Start Tunnel", variant="primary")
            stop_btn = gr.Button("Stop Tunnel")
            port_input = gr.Number(
                value=shared.cmd_opts.port or 7860,
                label="Port",
                precision=0
            )
        
        # Button actions
        def update_status():
            if TunnelState.active:
                return {
                    status: "Status: Active",
                    url_display: TunnelState.url or "Establishing connection...",
                    port_input: port_input.value
                }
            return {
                status: "Status: Inactive",
                url_display: "No active tunnel",
                port_input: port_input.value
            }
        
        def start_tunnel_wrapper(port):
            TunnelState.port = int(port)
            start_tunnel()
            return update_status()
        
        start_btn.click(
            fn=start_tunnel_wrapper,
            inputs=[port_input],
            outputs=[status, url_display, port_input]
        )
        
        stop_btn.click(
            fn=stop_tunnel,
            inputs=[],
            outputs=[status, url_display, port_input],
            _js="() => {setTimeout(() => window.location.reload(), 1000)}"
        )
        
        # Auto-update URL
        ui.load(
            fn=update_status,
            inputs=[],
            outputs=[status, url_display, port_input],
            every=3
        )
    
    return [(ui, "Pinggy Tunnel", "pinggy_tunnel")]

def cleanup():
    stop_tunnel()

def setup():
    # Register callbacks
    script_callbacks.on_app_started(on_app_started)
    script_callbacks.on_ui_tabs(on_ui_tabs)
    script_callbacks.on_script_unloaded(cleanup)
    
    # Add our custom flag to shared options
    if not hasattr(shared.cmd_opts, 'pinggy_tunnel'):
        shared.cmd_opts.pinggy_tunnel = False