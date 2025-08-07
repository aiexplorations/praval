# Jupyter Lab configuration for Praval development

c = get_config()

# Allow all IPs
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = 8888
c.ServerApp.open_browser = False

# Security settings for development
c.ServerApp.token = ''
c.ServerApp.password = ''
c.ServerApp.allow_root = True

# Enable extensions
c.ServerApp.jpserver_extensions = {
    'jupyterlab': True
}

# Set working directory
c.ServerApp.notebook_dir = '/app/notebooks'

# Allow external access
c.ServerApp.allow_origin = '*'
c.ServerApp.allow_credentials = True