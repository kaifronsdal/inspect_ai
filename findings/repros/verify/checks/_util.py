"""Shared helpers for 01-events checks."""

from harness import ViewerSession


def show_all_events(session: ViewerSession) -> None:
    """Switch the transcript event filter to **Debug** (= exclude nothing).

    The default filter (``kDefaultExcludeEvents``) hides ``sample_init``,
    ``sandbox``, ``state``, ``store``, ``branch`` — exactly the event types
    most F05.* repros target. The "None" preset means *show none*; "Debug"
    means *show everything* (``setFilteredEventTypes([])``).

    The PopOver wrapper is a 0×0 positioned div so Playwright reports it as
    invisible; fire the link's ``onClick`` via JS instead.
    """
    page = session.page
    # PopOver only mounts its children once the toggle button has been clicked
    # at least once (filterRef.current must resolve).
    page.locator("button").filter(has_text="Events:").first.click()
    session.wait_settled(network_idle=False)
    page.evaluate(
        """
        () => {
          const pop = document.querySelector('#transcript-filter-popover');
          if (!pop) return;
          const links = Array.from(pop.querySelectorAll('a'));
          const dbg = links.find(a => a.textContent.trim() === 'Debug');
          if (dbg) dbg.click();
        }
        """
    )
    session.wait_settled(network_idle=False, ms=500)
