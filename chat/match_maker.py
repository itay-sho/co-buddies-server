import random
import threading
import time
from chat.models import Conversation, ChatUser


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

    def add_to_pool(self, user_id, channel_name):
        self._pool[user_id] = channel_name
        self.perform_update()

    def _exists_in_pool(self, user_id):
        return user_id in self._pool

    def get_user_channel(self, user_id):
        if not self._exists_in_pool(user_id):
            return None

        return self._pool[user_id]

    def remove_from_pool_if_exist(self, user_id):
        if user_id in self._pool:
            del self._pool[user_id]

        self.perform_update()

    def perform_update(self):
        # self.seek_matches()
        pass

    def send_seek_message(self, message):
        # TODO: consider adding here a lobby message regarding to the matchmaking
        pass

    def seek_matches(self):
        while self._should_matchmake:
            for minutes_left in range(3, 0, -1):
                self.send_seek_message(minutes_left)
                time.sleep(20)

                if minutes_left > 1:
                    continue

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

    def _create_match(self, user_id1, user_id2):
        print(f'{user_id1} with {user_id2}')
        attendees_user_ids = [user_id1, user_id2]

        # calculating attendees dict
        chat_users = ChatUser.objects.filter(id__in=attendees_user_ids)
        attendees = {chat_user.id: chat_user.name for chat_user in chat_users}

        conversation = Conversation.create_conversation(attendees_user_ids)

        if self._matchcreated_callback is not None:
            self._matchcreated_callback(self._pool[user_id1], self._pool[user_id2], conversation.id, attendees)

        del self._pool[user_id1]
        del self._pool[user_id2]


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
