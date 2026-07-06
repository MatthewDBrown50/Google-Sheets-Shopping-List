"""Visual checks for trip list row buttons."""

from __future__ import annotations

from playwright.sync_api import Page


def trip_row_button(page: Page, name_pattern: str):
    import re

    return page.get_by_role("button", name=re.compile(name_pattern)).first


def trip_row_looks_crossed(button_locator) -> bool:
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
