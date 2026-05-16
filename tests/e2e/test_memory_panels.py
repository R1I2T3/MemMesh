import pytest

@pytest.mark.e2e
def test_memory_vector_panel_populates(page):
    page.locator("[data-testid='chat-input']").fill("Explain embeddings.")
    page.keyboard.press("Enter")
    
    # Wait for the explicit pipeline panels to appear
    page.wait_for_selector("[data-testid='chunk-card']", timeout=15000)
    count = page.locator("[data-testid='chunk-card']").count()
    assert count >= 1

@pytest.mark.e2e
def test_graph_panel_renders_relations(page):
    page.locator("[data-testid='chat-input']").fill("Who created the engine?")
    page.keyboard.press("Enter")
    
    page.wait_for_selector("[data-testid='graph-row']", timeout=15000)
    row_text = page.locator("[data-testid='graph-row']").first.inner_text()
    # E.g. "Subject --[RELATION]--> Object"
    assert "-->" in row_text
