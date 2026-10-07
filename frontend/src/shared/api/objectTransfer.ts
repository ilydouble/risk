/** S3 byte transfer is separate from enveloped business API requests. */
export function uploadObject(
  url: string,
  headers: Record<string, string>,
  file: File,
  progress: (value: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    for (const [name, value] of Object.entries(headers)) {
      if (!["content-length", "host"].includes(name.toLowerCase()))
        xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable)
        progress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () => reject(new Error("Object upload failed"));
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Object upload failed (${xhr.status})`));
    xhr.send(file);
  });
}
