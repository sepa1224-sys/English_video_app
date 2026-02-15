import script_gen

def main():
    print("=== Verify Reference Corpus Loading ===")
    for uni in ["todai", "kyoto", "osaka"]:
        s, f = script_gen.load_reference_corpus(uni)
        print(f"\n--- {uni} ---")
        print("SCRIPT:", "OK" if s else "MISSING")
        if s:
            print("SCRIPT PREVIEW:", (s[:100].replace("\n", " ") + "..."))
        print("FEATURES:", "OK" if (f is not None and f != "") else "MISSING/EMPTY")
        if f:
            print("FEATURES PREVIEW:", (str(f)[:100].replace("\n", " ") + "..."))

if __name__ == "__main__":
    main()
