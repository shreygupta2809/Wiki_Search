#!/usr/bin/python
import bisect
import math
import os
import Stemmer
import sys
import timeit

from processing import STOPWORDS


class SearchHandler:
    """Main Search Class"""

    def __init__(self, index_path: str):
        self.index_path = index_path
        self.file_per_page = 10000

        with open(os.path.join(index_path, 'first_words.txt'), 'r') as f:
            self.first_words = f.readline().rstrip().split(" ")

        with open(os.path.join(index_path, 'page_count.txt'), 'r') as f:
            self.total_pages = int(f.readline().rstrip())

        self.search_results = 10
        self.stemmer = Stemmer.Stemmer('english')

        self.index = {}
        self.token_set = {}
        self.token_dict = {}
        self.idf = {}
        self.doc_file_map = {str(k): set() for k in range(1, self.total_pages // self.file_per_page + 2)}
        self.doc_score = []
        self.results = []

    def parse_query(self, query: str):
        """Tokenize Individual Query to find Tokens and Fields"""
        query = query.replace(",", " ").split()
        pos = ''
        self.token_dict = {}
        self.token_set = {}
        for ind in range(len(query)):
            token = query[ind]
            query_list = token.split(':')
            if len(query_list) == 2:
                if token == ':':
                    continue
                elif token[0] == ':':
                    token = query_list[1]
                elif token[-1] == ':':
                    pos = query_list[0]
                    continue
                else:
                    pos = query_list[0]
                    token = query_list[1]
            else:
                if ind < len(query) - 1 and query[ind + 1][0] == ':':
                    pos = token
                    continue

            stemmed_token = self.stemmer.stemWord(token.lower())
            if stemmed_token in STOPWORDS:
                continue

            if stemmed_token in self.token_dict:
                self.token_dict[stemmed_token]["count"] += 1
                self.token_dict[stemmed_token]["tag"].add(pos)
            else:
                file_num = bisect.bisect_left(self.first_words, stemmed_token)
                file_num = file_num + 1 if file_num < len(self.first_words) and self.first_words[
                    file_num] == stemmed_token else file_num
                if file_num in self.token_set:
                    self.token_set[file_num].add(stemmed_token)
                else:
                    self.token_set[file_num] = {stemmed_token}

                self.token_dict[stemmed_token] = {"count": 1, "tag": set(pos)}

    def parse_query_file(self, query_file: str):
        """Parse Individual Query for Searching and display final results"""
        final_op = ""
        with open(query_file, 'r') as f:
            for _query in f:
                final_result = ""
                start = timeit.default_timer()
                query = _query.rstrip()
                self.parse_query(query=query)

                self.get_index()
                self.get_doc_score()
                self.get_titles()

                if len(self.results) == 0:
                    final_result += "NO RESULTS FOUND"
                else:
                    final_result = "\n".join(self.results)

                stop = timeit.default_timer()
                final_result += f"\n{stop - start}\n\n"

                final_op += final_result

                self.token_set = {}
                self.token_dict = {}
                self.index = {}
                self.idf = {}
                self.doc_file_map = {str(k): set() for k in range(1, self.total_pages // self.file_per_page + 2)}
                self.doc_score = []
                self.results = []

        with open("query_op.txt", 'w') as f:
            f.write(final_op)

    def get_doc_score(self) -> None:
        """Calculate Score for each doc by summation of score of each word"""
        for file_num, docs in self.doc_file_map.items():
            if len(docs) == 0:
                continue
            for _doc in docs:
                score = 0
                for word in self.index:
                    score += self.token_dict[word]["count"] * self.scoring_func(self.index[word][_doc],
                                                                                self.idf[word]) if _doc in self.index[
                        word] else 0

                if score != 0:
                    self.doc_score.append((_doc, score))

        self.doc_score = sorted(self.doc_score, key=lambda x: x[1], reverse=True)[:self.search_results]

    def scoring_func(self, tf: float, idf: float) -> float:
        """Scoring Function BM-15"""
        k1 = 1.2
        return idf * (1 + (tf * (k1 + 1)) / (tf + k1))

    def get_titles(self) -> None:
        """Get titles for each document"""
        for doc, score in self.doc_score:
            file_num = (doc - 1) // self.file_per_page + 1
            title_path = os.path.join(self.index_path, f"title_{file_num}.txt")
            with open(title_path, 'r') as f:
                lines = f.readlines()

            self.results.append(f"{doc}, {score}, " + lines[(doc - 1) % self.file_per_page].rstrip())

    def get_index(self) -> None:
        """Read index to get desired documents and posting lists"""
        for file, stem_words in self.token_set.items():
            if file == 0:
                continue
            index_path = os.path.join(self.index_path, f"index2_{file}.txt")
            with open(index_path, 'r') as f:
                for _line in f:
                    if len(self.token_set[file]) == 0:
                        break
                    token_line = _line.rstrip().split(" ")
                    word = token_line[0]
                    token_line = token_line[1:]
                    if word not in self.token_set[file]:
                        continue
                    self.token_set[file].remove(word)

                    docs = {doc_id: int(doc[0]) for _doc in token_line if
                            (doc := _doc.split("-")) != "" and (doc_id := int(doc[1])) != "" and (
                                    self.token_dict[word]["tag"].issubset(doc[-1]) or (
                                        self.token_dict[word]["tag"] == {"b"} and len(doc) <= 2))}

                    [self.doc_file_map[f"{(d - 1) // self.file_per_page + 1}"].add(d) for d in docs]
                    if word not in self.idf:
                        self.idf[word] = math.log(
                            1 + (self.total_pages - len(docs) + 0.5) / (len(docs) + 0.5))
                    self.index[word] = docs


def main():
    if len(sys.argv) < 3:
        print("Usage :: python3 search.py path_to_inverted_index queries.txt")
        sys.exit(0)

    handler = SearchHandler(sys.argv[1])
    handler.parse_query_file(sys.argv[2])


if __name__ == "__main__":
    main()
