import unittest
from .dictutil import merge_dictionaries, generate_patch, Patch

class DictUtils(unittest.TestCase):

    def test_merge(self):
        source = { "good": "morning", "people": { "homer": 1 } }
        new = { "bad": "day", "people": { "seth": 2 } }
        merge_dictionaries(source, new)
        self.assertEqual(source, {'good': 'morning', 'people': {'homer': 1, 'seth': 2}, 'bad': 'day'})

    def test_diff(self):
        original = { "version": 1, "hello": "fortran", "people": { "homer": 1 }, "sources": [1, 2] }
        updated = { "version": 2, "people": { "homer": 2, "seth": 3 }, "gamer": 4, "sources": [ 1, 3 ]}
        patch = generate_patch(original, updated)
 
        patch = Patch.from_json(patch.to_json())


        patch.apply_inplace(original)
        self.assertEqual(original, updated)
        # print(f'Original: {original}')


    

if __name__ == "__main__":
    unittest.main()