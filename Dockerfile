FROM tahv/mayapy:2025
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN ln -s /lib/x86_64-linux-gnu/libreadline.so.8 /lib/x86_64-linux-gnu/libreadline.so.7
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_TOOL_BIN_DIR=/usr/local/bin
ENV UV_PYTHON=/usr/autodesk/maya/bin/mayapy
ENTRYPOINT []
CMD ["mayapy", "-ic", "import maya.standalone; maya.standalone.initialize()"]
