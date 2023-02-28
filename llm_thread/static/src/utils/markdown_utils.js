/** @odoo-module **/

/**
 * Converts a Markdown string to HTML using the marked library.
 * @param {String} markdown - The Markdown text to convert.
 * @returns {String} The resulting HTML string.
 */
export function markdownToHtml(markdown) {
  return window.marked.parse(markdown);
}
