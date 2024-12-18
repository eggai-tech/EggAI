class ContextHolder:
    def __init__(self):
        self.context_map = {}

    def add_context(self, message_id, context_patch):
        if message_id not in self.context_map:
            self.context_map[message_id] = {}
        self.context_map[message_id].update(context_patch)

    def get_context(self, message_id):
        return self.context_map.get(message_id, {})
