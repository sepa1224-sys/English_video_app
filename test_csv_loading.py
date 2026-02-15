import script_gen

def test_loading():
    print("Testing CSV loading for Target 1900...")
    vocab = script_gen.load_vocabulary("ターゲット1900", day_number=1)
    print(f"Day 1 Vocabulary ({len(vocab)} items):")
    for item in vocab:
        print(item)

    vocab2 = script_gen.load_vocabulary("ターゲット1900", day_number=2)
    print(f"\nDay 2 Vocabulary ({len(vocab2)} items):")
    for item in vocab2:
        print(item)

    vocab3 = script_gen.load_vocabulary("ターゲット1900", day_number=3)
    print(f"\nDay 3 Vocabulary ({len(vocab3)} items) (Should wrap around or match logic):")
    for item in vocab3:
        print(item)

if __name__ == "__main__":
    test_loading()
