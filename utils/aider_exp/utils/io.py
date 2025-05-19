import git
import base64
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".pdf"}





def is_image_file(file_name):
    """
    Check if the given file name has an image file extension.

    :param file_name: The name of the file to check.
    :return: True if the file is an image, False otherwise.
    """
    file_name = str(file_name)  # Convert file_name to string
    return any(file_name.endswith(ext) for ext in IMAGE_EXTENSIONS)


def read_image(filename):
    try:
        with open(str(filename), "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
            return encoded_string.decode("utf-8")
    except OSError as err:
        print(f"{filename}: unable to read: {err}")
        return
    except FileNotFoundError:
        print(f"{filename}: file not found error")
        return
    except IsADirectoryError:
        print(f"{filename}: is a directory")
        return
    except Exception as e:
        print(f"{filename}: {e}")
        return


def read_text(filename, silent=False):
    if is_image_file(filename):
        return read_image(filename)

    try:
        with open(str(filename), "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        if not silent:
            print(f"{filename}: file not found error")
        return
    except IsADirectoryError:
        if not silent:
            print(f"{filename}: is a directory")
        return
    except OSError as err:
        if not silent:
            print(f"{filename}: unable to read: {err}")
        return
    except UnicodeError as e:
        if not silent:
            print(f"{filename}: {e}")
            print("Use --encoding to set the unicode encoding.")
        return



