"""Return True when the trip row button looks crossed off (red + strikethrough)."""

from __future__ import annotations


def trip_row_looks_crossed(button_locator) -> bool:
    """Crossed rows use kind=primary plus red strikethrough label styling."""
    return button_locator.evaluate(
        """(el) => {
        const p = el.querySelector('p') || el;
        const style = getComputedStyle(p);
        const struck = style.textDecorationLine.includes('line-through');
        const color = style.color || '';
        const red = color.includes('239, 83, 80') || color.includes('ef5350');
        const kind = el.getAttribute('kind');
        return struck || (kind === 'primary' && red);
      }"""
    )
