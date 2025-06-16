from abc import abstractmethod


class SyncBase:

    @abstractmethod
    def get_rss_list(self):
        pass

    @abstractmethod
    def insert_rss(self):
        pass
