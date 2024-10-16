import io
import websockets.asyncio.client as websockets
import zipfile
import os


async def stream_zip_directory(ws: websockets.ClientConnection, folder_path: str):
    """Stream a folder as a zip archive over WebSocket in chunks."""
    try:
        # Создаем временный буфер для zip-архива
        with io.BytesIO() as zip_buffer:
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Проходимся по файлам в директории и добавляем их в архив
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        archive_name = os.path.relpath(file_path, folder_path)  # относительный путь в архиве
                        zip_file.write(file_path, arcname=archive_name)

                        # Flush the current state of the ZIP buffer and send the current chunk
                        zip_buffer.seek(0, io.SEEK_END)
                        current_size = zip_buffer.tell()
                        if current_size > 0:
                            zip_buffer.seek(0)
                            chunk = zip_buffer.read(current_size)
                            await ws.send(chunk)
                            zip_buffer.seek(0)
                            zip_buffer.truncate(0)  # очищаем буфер для следующего чанка

                # Закрываем zip и отправляем финальный кусок архива
                zip_buffer.seek(0, io.SEEK_END)
                final_size = zip_buffer.tell()
                if final_size > 0:
                    zip_buffer.seek(0)
                    await ws.send(zip_buffer.read(final_size))

        print(f"Теку {folder_path} відправлено на сервер.")

    except Exception as err:
        print(f"Помилка при стрімінгу zip архіва: {err}")


async def stream_file(ws: websockets.ClientConnection, file_path: str):
    """Stream file in chunks over WebSocket."""
    try:
        file_size = os.path.getsize(file_path)
        # Send file size first
        await ws.send(str(file_size))

        # Stream the file in chunks
        with open(file_path, "rb") as file:
            while chunk := file.read(1024 * 1024):  # Stream by 1 MB chunks
                await ws.send(chunk)

        print(f"Файл {file_path} відправлено на сервер.")

    except Exception as err:
        print(f"Помилка при стрімінгу файла: {err}")


async def handle_download_request(message, base: str, stream_endpoint: str, session_id: str):
    """Handle 'download' request: connect to WebSocket and stream file or folder as ZIP."""
    request_id = message["requestId"]
    url = message["url"]
    path = url.replace("root", base)

    websocket_url = f"{stream_endpoint}/{session_id}"

    async with websockets.connect(websocket_url, additional_headers={"X-Stream-Channel": request_id}) as ws:
        # Если это файл, стримим файл
        if os.path.isfile(path):
            await stream_file(ws, path)
        # Если это папка, стримим папку как zip-архив
        elif os.path.isdir(path):
            await stream_zip_directory(ws, path)
        else:
            print(f"Шлях {path} не є файлом або текою.")
