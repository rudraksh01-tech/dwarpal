// Just enough Markdown for agent answers: paragraphs, **bold**, lists and tables.

function inline(text, keyPrefix) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={`${keyPrefix}-${index}`}>{part.slice(2, -2)}</strong>
    ) : (
      part
    )
  );
}

function isTableRow(line) {
  return line.trim().startsWith("|") && line.trim().endsWith("|");
}

function cells(line) {
  return line.trim().slice(1, -1).split("|").map((cell) => cell.trim());
}

export default function Markdown({ text }) {
  const lines = (text || "").split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (isTableRow(line)) {
      const rows = [];
      while (index < lines.length && isTableRow(lines[index])) rows.push(lines[index++]);
      const body = rows.filter((row) => !/^\|\s*:?-{2,}/.test(row.trim()));
      const [head, ...rest] = body.map(cells);
      blocks.push(
        <div className="md-table" key={`t${index}`}>
          <table>
            <thead><tr>{head.map((cell, i) => <th key={i}>{inline(cell, `h${i}`)}</th>)}</tr></thead>
            <tbody>
              {rest.map((row, r) => (
                <tr key={r}>{row.map((cell, i) => <td key={i}>{inline(cell, `c${r}${i}`)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[index])) {
        items.push(lines[index++].replace(/^\s*([-*]|\d+\.)\s+/, ""));
      }
      blocks.push(<ul key={`l${index}`}>{items.map((item, i) => <li key={i}>{inline(item, `li${i}`)}</li>)}</ul>);
      continue;
    }

    if (line.trim() && !/^-{3,}$/.test(line.trim())) {
      blocks.push(<p key={`p${index}`}>{inline(line.replace(/^#+\s*/, ""), `p${index}`)}</p>);
    }

    index++;
  }

  return <div className="md">{blocks}</div>;
}
