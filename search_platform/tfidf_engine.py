import math

class TFIDFEngine:
    def compute(self, num_docs, doc_term_counts, doc_total_words):
        """
        Computes TF-IDF index from term counts.
        doc_term_counts: dict mapping url -> {term: count}
        doc_total_words: dict mapping url -> total word count
        Returns: inverted_index { term: [[url, score], ...] }
        """
        df = {}
        for url, counts in doc_term_counts.items():
            for term in counts.keys():
                df[term] = df.get(term, 0) + 1

        inverted_index = {}
        for url, counts in doc_term_counts.items():
            total_words = doc_total_words[url]
            if total_words == 0:
                continue
                
            for term, count in counts.items():
                tf = count / total_words
                idf = math.log(1.0 + (num_docs / (1.0 + df[term])))
                tf_idf = tf * idf
                
                if term not in inverted_index:
                    inverted_index[term] = []
                inverted_index[term].append([url, tf_idf])

        for term in inverted_index:
            inverted_index[term].sort(key=lambda x: x[1], reverse=True)

        return inverted_index
