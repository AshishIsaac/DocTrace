from doctrace.chunk import chunk_text, normalize


def test_empty_and_noise():
    assert chunk_text("") == []
    assert chunk_text("  \n\n 12 \n") == []


def test_short_text_is_one_chunk():
    assert chunk_text("Hello world. This is a note.") == ["Hello world. This is a note."]


def test_chunks_respect_size_and_overlap():
    text = " ".join(f"Sentence number {i} is here." for i in range(300))
    chunks = chunk_text(text, size=300, overlap=60)
    assert len(chunks) > 10
    assert max(map(len, chunks)) <= 300
    # consecutive chunks share some text
    assert chunks[0].split()[-1] in chunks[1]


def test_long_word_is_hard_split():
    chunks = chunk_text("x" * 2500, size=1000, overlap=0)
    assert [len(c) for c in chunks] == [1000, 1000, 500]


def test_normalize_whitespace():
    assert normalize("a \t b\r\n\r\n\r\nc  ") == "a b\n\nc"
