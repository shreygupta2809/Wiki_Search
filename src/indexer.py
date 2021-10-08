#!/usr/bin/python
import heapq
from glob import glob
import os
from pathlib import Path
import resource
import sys
import timeit
import xml.sax.handler

from processing import process_data


class WikiHandler(xml.sax.handler.ContentHandler):
    """Main Indexing Class"""

    def __init__(self, path_to_index: str, path_to_stat: str):
        super().__init__()
        self.index_path = os.path.join(os.getcwd(), path_to_index)
        self.stat_path = os.path.join(os.getcwd(), path_to_stat)
        self.title_start = 0
        self.id_start = 0
        self.id_done = 0
        self.text_start = 0
        self.page_start = 0
        self.title = ""
        self.id = ""
        self.text = ""
        self.global_data = {}
        self.total_page_count = 0
        self.file_count = 0
        self.title_file_count = 0
        self.titles = []
        self.cur_file_size = 0
        self.stage2_first_words = ""

    def startElement(self, tag, attributes):
        """Start tag reading"""
        if tag == "page":
            self.page_start = 1
        elif tag == "title":
            self.title_start = 1
        elif tag == "id" and not self.id_done:
            self.id_start = 1
        elif tag == "text":
            self.text_start = 1

    def characters(self, content):
        """Read the text character by character"""
        if self.title_start:
            self.title += content
        elif self.id_start:
            self.id += content
        elif self.text_start:
            self.text += content

    def endElement(self, tag):
        """End tag Reading and create Postings Doc for each document"""
        if tag == "page":
            self.page_start = 0
            self.title = self.title.lower()
            if not self.title.startswith(("wikipedia:", "file:", "category:", "template:", "portal:", "help:")):
                self.total_page_count += 1
                self.titles.append(self.title)
                self.merge_dicts(process_data(ID=self.total_page_count, title=self.title, text=self.text))
            self.title = ""
            self.id = ""
            self.text = ""
            self.id_done = 0
        elif tag == "title":
            self.title_start = 0
        elif tag == "id":
            self.id_start = 0
            self.id_done = 1
        elif tag == "text":
            self.text_start = 0

    def merge_dicts(self, doc_tokens: dict) -> None:
        """Merge Postings Dict for the documents"""
        for token, val in doc_tokens.items():

            doc_list = list(doc_tokens[token].values())
            doc_string = f"{doc_list[0]}-" + doc_list[1]
            if len(doc_list[-1]):
                doc_string += "-" + "".join(doc_list[-1])
            self.cur_file_size += len(doc_string)
            if token in self.global_data:
                self.cur_file_size += 1
                self.global_data[token] += " " + doc_string
            else:
                self.cur_file_size += len(token)
                self.global_data[token] = doc_string

        self.check_stage(stage=1, is_finish=False)

    def index_creator(self, stage: int) -> None:
        """Write postings list to the files depending on the stage"""
        sorted_global_data = sorted(self.global_data.items())
        index_string = "\n".join([k + " " + v for k, v in sorted_global_data])
        if stage == 2:
            self.stage2_first_words += " " + sorted_global_data[0][0] if len(self.stage2_first_words) else \
                sorted_global_data[0][0]

        self.file_count += 1
        path_to_index = os.path.join(self.index_path, f'index{stage}_{self.file_count}.txt')

        with open(path_to_index, 'w') as f:
            f.write(index_string)

    def title_index(self) -> None:
        """Write titles files depending on the stage"""
        title_string = "\n".join(self.titles)

        self.title_file_count += 1
        path_to_index = os.path.join(self.index_path, f'title_{self.title_file_count}.txt')

        with open(path_to_index, 'w') as f:
            f.write(title_string)

    def check_stage(self, stage: int, is_finish: bool) -> None:
        """Stage Dependent Writing"""
        if (stage == 1 and self.cur_file_size >= 6e7 and not is_finish) or (
                stage == 2 and self.cur_file_size >= 2e7 and not is_finish) or (is_finish and self.cur_file_size):
            self.index_creator(stage=stage)
            self.global_data = {}
            self.cur_file_size = 0

        if stage == 1 and ((len(self.titles) >= 1e4 and not is_finish) or (len(self.titles) and is_finish)):
            self.title_index()
            self.titles = []

    def merge_files(self):
        """Merge stage 1 index files using heaps to create stage 2 index which is smaller, write all extra files
        needed in searching """
        stage1_file_count = self.file_count
        left_files = stage1_file_count
        self.file_count = 0
        heap = []
        files = {}
        words = {}
        total_word_count = 0

        for i in range(1, stage1_file_count + 1):
            file_name = os.path.join(self.index_path, f'index1_{i}.txt')
            files[i] = open(file_name, 'r')
            line = files[i].readline().rstrip()
            words[i] = line.split(" ", 1)
            heapq.heappush(heap, (words[i][0], i))

        while left_files:
            word = heap[0][0]

            postings_list = ""
            total_word_count += 1

            while len(heap) and word == heap[0][0]:
                _, file = heapq.heappop(heap)
                postings_list += " " + words[file][1] if len(postings_list) else words[file][1]
                line = files[file].readline().rstrip()
                if line == '':
                    files[file].close()
                    left_files -= 1
                else:
                    words[file] = line.split(" ", 1)
                    heapq.heappush(heap, (words[file][0], file))

            self.global_data[word] = postings_list
            self.cur_file_size += len(word) + len(postings_list)

            self.check_stage(stage=2, is_finish=False)

        self.check_stage(stage=2, is_finish=True)

        stage1_files = os.path.join(self.index_path, 'index1_*.txt')
        [os.remove(f) for f in glob(stage1_files)]

        output_dir = Path(self.index_path)
        index_file_size = sum(f.stat().st_size for f in output_dir.glob('*') if f.is_file())
        stat_string = f"Index size in GB: {index_file_size / 1e9}\nNumber of files in which the inverted index is " \
                      f"split: {self.file_count + self.title_file_count + 2}\nNumber of tokens in the inverted " \
                      f"index: {total_word_count} "
        with open(self.stat_path, 'w') as f:
            f.write(stat_string)

        file_count_path = os.path.join(self.index_path, 'page_count.txt')
        with open(file_count_path, 'w') as f:
            f.write(str(self.total_page_count))

        first_words_path = os.path.join(self.index_path, 'first_words.txt')
        with open(first_words_path, 'w') as f:
            f.write(self.stage2_first_words)


def main():
    if len(sys.argv) != 4:
        print("Usage :: python3 indexer.py path_to_xml path_to_inverted_index index_name")
        sys.exit(0)

    path_to_wiki = sys.argv[1]
    path_to_index = sys.argv[2]
    path_to_stat = sys.argv[3]
    parser = xml.sax.make_parser()
    handler = WikiHandler(path_to_index=path_to_index, path_to_stat=path_to_stat)
    parser.setContentHandler(handler)
    parser.parse(path_to_wiki)
    handler.check_stage(stage=1, is_finish=True)
    start1 = timeit.default_timer()
    handler.merge_files()
    stop1 = timeit.default_timer()
    print(stop1 - start1)
    print("Memory taken: ", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (10 ** 6), " GB")


if __name__ == "__main__":
    start = timeit.default_timer()
    main()
    stop = timeit.default_timer()
    print(stop - start)
