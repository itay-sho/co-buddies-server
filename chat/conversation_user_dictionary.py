class ConversationUserDictionary:
    LOBBY_CONVERSATION_ID = 1

    def __init__(self):
        self._users_to_conversations_dict = {}
        self._conversations_to_user_dict = {ConversationUserDictionary.LOBBY_CONVERSATION_ID: set([])}

    def _remove_from_both_dicts(self, user_id, conversation_id, is_safe):
        if is_safe:
            self._conversations_to_user_dict[conversation_id].discard(user_id)
            self._users_to_conversations_dict.pop(user_id, '')
        else:
            self._conversations_to_user_dict[conversation_id].remove(user_id)
            del self._users_to_conversations_dict[user_id]

    '''
    return conversation_id if conversation was closed due to this operation, None otherwise
    '''
    def remove_user_from_conversation(self, user_id, conversation_id, is_safe=False):
        self._remove_from_both_dicts(user_id, conversation_id, is_safe)

        if (
                len(self._conversations_to_user_dict[conversation_id]) <= 1 and
                conversation_id != ConversationUserDictionary.LOBBY_CONVERSATION_ID
        ):
            self._close_conversation(conversation_id, is_safe)
            return conversation_id

    def _close_conversation(self, conversation_id, is_safe):
        for user_id in self._conversations_to_user_dict[conversation_id].copy():
            self._remove_from_both_dicts(user_id, conversation_id, is_safe)

        del self._conversations_to_user_dict[conversation_id]

    def add_user_to_conversation(self, user_id, conversation_id):
        if conversation_id not in self._conversations_to_user_dict:
            self._conversations_to_user_dict[conversation_id] = set([])

        self._conversations_to_user_dict[conversation_id].add(user_id)
        self._users_to_conversations_dict[user_id] = conversation_id

    def user_disconnect(self, user_id):
        return self.remove_user_from_conversation(user_id, self._users_to_conversations_dict[user_id])

    def conversation_close(self, conversation_id):
        for user in self._conversations_to_user_dict[conversation_id].copy():
            self.remove_user_from_conversation(user, conversation_id)

    def leave_any_previous_conversations_and_join(self, user_id, conversation_id):
        if user_id in self._users_to_conversations_dict:
            self.remove_user_from_conversation(user_id, self._users_to_conversations_dict[user_id])

        self.add_user_to_conversation(user_id, conversation_id)

    def get_conversation_attendees(self, conversation_id):
        return self._conversations_to_user_dict[conversation_id]

    def get_user_conversation(self, user_id):
        return self._users_to_conversations_dict[user_id]