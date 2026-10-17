import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useLang } from "@/shared/lib/useLang";

/** Answers and reasoning share the same safe Markdown rendering policy. */
export function MessageMarkdown({ text }: { text: string }) {
  const { pick } = useLang();
  return <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{
    a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    img: ({ alt }) => <span>[{alt || pick("图片", "Image")}]</span>,
    table: ({ children }) => <div className="overflow-x-auto"><table>{children}</table></div>,
  }}>{text}</ReactMarkdown>;
}
