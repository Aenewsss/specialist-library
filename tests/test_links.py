from app.search.links import SourcePosition, build_link


def test_youtube_link_points_to_the_second():
    position = SourcePosition("youtube", "ignorado", external_id="qgikRaQkPGU", start_s=754)
    assert build_link(position) == "https://www.youtube.com/watch?v=qgikRaQkPGU&t=754s"


def test_book_link_points_to_the_page():
    assert build_link(SourcePosition("livro", "file.pdf", page=12)) == "file.pdf#page=12"


def test_other_sources_use_the_original_url():
    assert build_link(SourcePosition("web", "https://blog/post")) == "https://blog/post"
