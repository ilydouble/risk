interface HighlightProps {
  text: string;
  query: string;
}

export default function Highlight({ text, query }: HighlightProps) {
  const keyword = query.trim();
  if (!keyword) {
    return <>{text}</>;
  }

  const index = text.toLowerCase().indexOf(keyword.toLowerCase());
  if (index === -1) {
    return <>{text}</>;
  }

  return (
    <>
      {text.slice(0, index)}
      <mark className="rounded bg-primary-500/25 px-0.5 text-primary-300">
        {text.slice(index, index + keyword.length)}
      </mark>
      {text.slice(index + keyword.length)}
    </>
  );
}