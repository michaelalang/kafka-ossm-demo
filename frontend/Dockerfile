FROM registry.redhat.io/ubi9/python-39
# Add application sources to a directory that the assemble script expects them
# and set permissions so that the container runs without root access
USER 0
COPY app.py /tmp/src/app.py
COPY requirements.txt /tmp/src/requirements.txt
RUN /usr/bin/fix-permissions /tmp/src
USER 1001

# Install the dependencies
RUN /usr/libexec/s2i/assemble

ENV APP_SCRIPT app.py

# Set the default command for the resulting image
CMD /usr/libexec/s2i/run
