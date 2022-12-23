/** @odoo-module **/

/**
 * Converts a Markdown string to HTML using the marked library.
 * @param {string} markdown - The Markdown text to convert.
 * @returns {string} The resulting HTML string.
 */
export function markdownToHtml(markdown) {
  return window.marked.parse(markdown);
}
