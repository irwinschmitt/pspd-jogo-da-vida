# Start from the same base image your workers are using
FROM bitnami/spark:3.5.1

# Switch to the root user to install packages and set permissions
USER root

# Copy your application files into the /app directory
COPY main.py /app/main.py
COPY requirements.txt /app/requirements.txt

# Install the Python dependencies from your requirements file
RUN pip install --no-cache-dir -r /app/requirements.txt

# --- FIX: Use the correct numeric UID (1001) and GID (0) ---
# The Bitnami container's non-root user has UID 1001 and belongs to the root group (GID 0).
RUN chown -R 1001:0 /app
# -----------------------------------------------------------

# Switch back to the default non-root user (UID 1001) for security
USER 1001
