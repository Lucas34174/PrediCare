// web/src/lib/pdfExtract.ts
export async function extractPdfText(file: File): Promise<string> {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    throw new Error('Seuls les fichiers PDF sont acceptés.')
  }
  if (file.size > 5 * 1024 * 1024) {
    throw new Error('Le fichier dépasse 5 Mo.')
  }

  // Import dynamique → pas dans le bundle initial
  const pdfjs = await import('pdfjs-dist')
  // Worker via CDN (le plus simple, pas de config Vite)
  pdfjs.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

  const arrayBuffer = await file.arrayBuffer()
  const pdf = await pdfjs.getDocument({ data: arrayBuffer }).promise

  let fullText = ''
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i)
    const content = await page.getTextContent()
    const pageText = content.items
    
      .map((item) => ('str' in item ? item.str : ''))
      .join(' ')
    fullText += `\n${pageText}`
  }
  return fullText.trim()
}