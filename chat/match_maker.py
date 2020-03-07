import random
import threading
import time
from chat.models import Conversation


class MatchMaker:
    def __init__(self, matchcreated_callback):
        self._matchcreated_callback = matchcreated_callback
        self._pool = {}
        self._should_matchmake = False
        self._seek_matches_thread = None
        self.start_matchmaking()

    def start_matchmaking(self):
        self._should_matchmake = True
        self._seek_matches_thread = threading.Thread(target=self.seek_matches)
        self._seek_matches_thread.daemon = True
        self._seek_matches_thread.start()

    def stop_matchmaking(self):
        if self._seek_matches_thread.is_alive():
            self._should_matchmake = False
            self._seek_matches_thread.join()

    def add_to_pool(self, channel_name, user_id):
        self._pool[channel_name] = user_id
        self.perform_update()

    def remove_from_pool(self, channel):
        if channel in self._pool:
            del self._pool[channel]
        self.perform_update()

    def perform_update(self):
        # self.seek_matches()
        pass

    def seek_matches(self):
        while self._should_matchmake:
            time.sleep(1)

            pool_items = list(self._pool.keys())
            while len(pool_items) > 0:
                random_1 = random.choice(pool_items)
                pool_items.remove(random_1)

                if len(pool_items) == 0:
                    print(f'{random_1} alone :-(')
                    break

                random_2 = random.choice(pool_items)
                pool_items.remove(random_2)
                self._create_match(random_1, random_2)
            # print("============\n")

    def _create_match(self, channel1, channel2):
        print(f'{self._pool[channel1]} with {self._pool[channel2]}')
        attendees_user_ids = [self._pool[channel1],  self._pool[channel2]]
        conversation = Conversation.create_conversation(attendees_user_ids)

        del self._pool[channel1]
        del self._pool[channel2]

        if self._matchcreated_callback is not None:
            self._matchcreated_callback(channel1, channel2, conversation.id)


# def main():
#     matcher = MatchMaker(None)
#     dict = {
#         'a': 0,
#         'b': 0,
#         'c': 0,
#         'd': 0,
#         'e': 0,
#     }
#
#     for key, val in dict.items():
#         matcher.add_to_pool(key, val)
#
#     time.sleep(3)
#     matcher.add_to_pool('f', 0)
#     time.sleep(3)
#     print('killing thread')
#     matcher.stop_matchmaking()
#     print('bye')
#
#
# if __name__ == '__main__':
#     main()
