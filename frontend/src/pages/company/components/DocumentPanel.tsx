import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { motion } from "motion/react";
import Card from "@/shared/ui/Card";
import * as DocumentApi from "@/entities/document/api/documentApi";
import type { ResponseListDocuments } from "@/shared/api/dto";
import { handleApiError } from "@/shared/api/http";
import { useLang } from "@/shared/lib/useLang";

type Document = ResponseListDocuments["items"][number];

export default function DocumentPanel({ companyId }: { companyId: string }) {
  const { isEn } = useLang();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const reload = async () => {
    const data = await DocumentApi.requestListDocuments({ companyId });
    setDocuments(data.items);
  };

  useEffect(() => {
    let active = true;
    DocumentApi.requestListDocuments({ companyId })
      .then((data) => { if (active) setDocuments(data.items); })
      .catch((failure) => { if (active) setError(handleApiError(failure)); });
    return () => { active = false; };
  }, [companyId]);

  const upload = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    try {
      const signed = await DocumentApi.requestCreateUpload({
        companyId, filename: file.name, contentType: file.type || "application/octet-stream", size: file.size,
      });
      // S3 is a separate byte channel. Use the signed URL and headers unchanged.
      const transfer = await fetch(signed.url, {
        method: "PUT", headers: signed.headers, body: file, credentials: "omit",
      });
      if (!transfer.ok) throw new Error("Object upload failed");
      await DocumentApi.requestCompleteUpload({ documentId: signed.documentId });
      await reload();
      setFile(null);
      setOpen(false);
    } catch (failure) {
      setError(handleApiError(failure, {
        DOCUMENT_SIZE_MISMATCH: isEn ? "File size mismatch" : "文件大小与声明不符",
        DOCUMENT_UPLOAD_INCOMPLETE: isEn ? "Upload incomplete" : "文件尚未上传完成",
      }));
    } finally {
      setBusy(false);
    }
  };

  const download = async (document: Document) => {
    setError("");
    try {
      const signed = await DocumentApi.requestCreateDownload({ documentId: document.id });
      const transfer = await fetch(signed.url, { credentials: "omit" });
      if (!transfer.ok) throw new Error("Object download failed");
      const objectUrl = URL.createObjectURL(await transfer.blob());
      const anchor = documentElement();
      anchor.href = objectUrl;
      anchor.download = document.filename;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (failure) {
      setError(handleApiError(failure));
    }
  };

  return (
    <Card title={isEn ? "Documents" : "企业文件"} subtitle={isEn ? "Presigned upload and download demo" : "预签名上传与下载演示"} icon="ri-file-upload-line" bodyClassName="p-4" action={
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Trigger asChild><button type="button" className="rounded-md bg-primary-500 px-3 py-2 text-xs text-background-50">{isEn ? "Upload file" : "上传文件"}</button></Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
          <Dialog.Content asChild>
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="fixed left-1/2 top-1/2 z-50 w-[min(440px,90vw)] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-background-300 bg-background-100 p-5 text-foreground-900">
              <Dialog.Title className="text-base font-semibold">{isEn ? "Upload document" : "上传企业文件"}</Dialog.Title>
              <Dialog.Description className="mt-1 text-xs text-foreground-500">{isEn ? "Maximum 10 MB. Demo storage only." : "最大 10 MB，仅用于演示。"}</Dialog.Description>
              <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-5 block w-full text-xs" />
              {error && <p role="alert" className="mt-3 text-xs text-accent-400">{error}</p>}
              <div className="mt-5 flex justify-end gap-2"><Dialog.Close asChild><button type="button" className="rounded-md border border-background-300 px-3 py-2 text-xs">{isEn ? "Cancel" : "取消"}</button></Dialog.Close><button type="button" disabled={!file || file.size > 10_000_000 || busy} onClick={upload} className="rounded-md bg-primary-500 px-3 py-2 text-xs text-background-50 disabled:opacity-50">{busy ? "…" : isEn ? "Upload" : "上传"}</button></div>
            </motion.div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    }>
      {error && !open && <p role="alert" className="mb-3 text-xs text-accent-400">{error}</p>}
      {documents.length === 0 ? <p className="text-xs text-foreground-500">{isEn ? "No documents yet" : "暂无文件"}</p> : <ul className="space-y-2">{documents.map((document) => <li key={document.id} className="flex items-center justify-between gap-3 rounded-md border border-background-200 px-3 py-2 text-xs"><span className="min-w-0 truncate">{document.filename}</span><button type="button" onClick={() => download(document)} className="shrink-0 text-primary-400 hover:underline">{isEn ? "Download" : "下载"}</button></li>)}</ul>}
    </Card>
  );
}

function documentElement(): HTMLAnchorElement {
  const anchor = document.createElement("a");
  document.body.appendChild(anchor);
  window.setTimeout(() => anchor.remove(), 0);
  return anchor;
}
