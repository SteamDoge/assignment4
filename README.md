# assignment4

# UDP 文件传输系统

这是一个基于 UDP 协议的简单文件传输系统，包含一个服务器端和一个客户端。

## 文件说明

*   `UDPServer.py`: 服务器端程序，负责接收客户端的下载请求并传输文件。
*   `UDPClient.py`: 客户端程序，负责向服务器请求并下载文件。
*   `files/`: (目录) 服务器端存放可供下载文件的位置。**请确保将要传输的文件放在此目录下。**
*   `client_files/`: (目录) 客户端下载文件后保存的位置。此目录会在客户端运行时自动创建。
*   `files.txt`: 客户端读取的文件列表，列出需要从服务器下载的文件名（每行一个）。

## 如何运行

### 1. 准备工作

*   确保你安装了 Python 3。
*   在 `files/` 目录下放置一些你想要传输的文件（例如 `small.txt`, `medium.txt`, `kami.png` 等）。
*   创建或编辑 `files.txt` 文件，列出你希望客户端下载的文件名，例如：

    ```
    small.txt
    medium.txt
    kami.png
    ```

### 2. 启动服务器

在命令行中，进入项目根目录，然后运行：

```bash
python UDPServer.py <端口号>

eg:

python UDPServer.py 12345
python UDPClient.py localhost 12345 files.txt
```

