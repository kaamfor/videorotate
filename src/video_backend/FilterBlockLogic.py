from collections.abc import MutableMapping
from typing import Optional, Any

import videorotate_constants

# Root-less 'tree'
# TODO: Inappropiate naming - filter vs. filter dict
# TODO: optimize for search


class FilterBlockLogic:
    def __init__(self) -> None:

        # {<level>: {<T>: {<object>: {<infos>}, ..}, ..}, ..}
        self._filters = {}

    # return filter-related infos dictionary
    def add_filter(self,
                   filter_id,
                   parent_id=None,
                   initial_keyvalues: Optional[MutableMapping] = None) -> MutableMapping:
        assert isinstance(initial_keyvalues, MutableMapping)

        if videorotate_constants.DEBUG:
            import sys
            print('BEFORE', self._filters)
            sys.stdout.flush()

        if initial_keyvalues is None:
            initial_keyvalues = {}

        level = self._find_input_leaf_level(parent_id)

        placement = self._safe_leaf_placement(level, filter_id)

        if videorotate_constants.DEBUG:
            import sys
            print('PLCMENT', level, filter_id, placement)
            sys.stdout.flush()


        placement.update(initial_keyvalues)

        placement['parent_id'] = parent_id
        placement['filter_id'] = filter_id
        
        if videorotate_constants.DEBUG:
            import sys
            print('AFTER', self._filters)
            sys.stdout.flush()

        return placement

        # info_match is None -> all matches
        # return list<description>

    def prepare_custom_filter_container(self, container: MutableMapping, filter_id, parent_id=None):
        assert isinstance(container, MutableMapping)

        level = self._find_input_leaf_level(parent_id)

        self._safe_leaf_placement(level, filter_id, container)

    def _find_input_leaf_level(self, parent_id):
        if parent_id is None:
            # Root filter
            level = 0
        else:
            # Non-root filter
            parent_descr = self.get_filter_by_id(parent_id)

            if parent_descr is None:
                raise ValueError("Filter parent not found")

            level = int(parent_descr['level'])+1

        return level

    # return filter-related infos dictionary
    def list_matching_filters(self, info_match: dict = None, min_level: int = None, max_level: int = None):
        no_min_limit, no_max_limit = False, False
        if min_level is None:
            min_level = 0
            no_min_limit = True
        if max_level is None:
            max_level = -1
            no_max_limit = True
        assert isinstance(min_level, int)
        assert isinstance(max_level, int)

        assert info_match is None or isinstance(info_match, MutableMapping)
        all_matches = info_match is None

        def filter_matches(filter_descr: MutableMapping):
            return all([filter_descr.get(k) == v for k, v in info_match.items()])

        matching_list = []

        for level_i, level in self._filters.items():

            if (no_min_limit or min_level <= level_i) and (no_max_limit or max_level >= level_i):
                for type_, type_i in level.items():

                    for filter_id, object_i in type_i.items():

                        check = all_matches or filter_matches(object_i)

                        if check:
                            parent = object_i.get('parent_id')

                            matching_list.append({
                                'object': object_i,
                                'level': level_i,
                                'parent_id': parent
                            })

                        # if videorotate_constants.DEBUG:
                        #     import sys
                        #     print('FILTER_SEARCH', filter_id, check, object_i)
                        #     sys.stdout.flush()

        # if videorotate_constants.DEBUG:
        #     import sys
        #     #print('LISTIG', matching_list)
        #     list(map(lambda e: print('LISTIG', e['object']['filter']), matching_list))
        #     sys.stdout.flush()
        

        return matching_list

    # return list<description>
    def get_children_filters(self, parent_id):
        assert parent_id is not None
        parent_descr = self.get_filter_by_id(parent_id)

        if parent_descr is None:
            raise ValueError("Filter parent not found")

        level = int(parent_descr['level'])+1

        return self.list_matching_filters(
            {'parent_id': parent_id},
            min_level=level,
            max_level=level
        )

    # return description
    def get_filter_by_id(self, filter_id):
        search_parent = None
        search_item_dict = None
        search_level = 0

        for level_i in self._filters:
            search_item_dict = self._safe_filter_getter(level_i, filter_id)
            if search_item_dict is not None:
                search_level = level_i
                break

        if search_item_dict is not None:
            return {
                'level': search_level,
                'filter_obj': search_item_dict
            }

        return None

    def delete_filter(self, filter_id) -> bool:
        return self.pop_filter(filter_id)[1]

    # return description, bool
    def pop_filter(self, filter_id):
        description = self.get_filter_by_id(filter_id)

        if description['filter_id'] is not filter_id:
            raise ValueError('Filter does not exists.')

        indicator = self.__lower_item_level(description, True)

        level = description['level']
        del self._filters[level][type(filter_id)][filter_id]

        if len(self._filters[level][type(filter_id)]) == 0:
            del self._filters[level][type(filter_id)]

        if len(self._filters[level]) == 0:
            del self._filters[level]

        return description, indicator

    def __lower_item_level(self, item_description: MutableMapping, only_children: bool = False):
        assert isinstance(item_description, MutableMapping)

        if not only_children:
            item_description['level'] -= 1

        return all([self.__lower_item_level(child)
                    for child in self.get_children_filters(item_description['filter_id'])]
                   )

    # return filter_dict<Filter,filter_infos_dict>|None
    def _safe_filter_selector(self, level: int, type_):
        # Is level exists?
        if level in self._filters:
            # Is index exists?
            if type_ in self._filters[level]:
                return self._filters[level][type_]
            return None
        return None

    # return filter_infos_dict|None
    def _safe_filter_getter(self, level: int, filter_id):
        selected = self._safe_filter_selector(level, type(filter_id))
        if selected is not None:
            return selected.get(filter_id)
        return None

    # return filter_infos_dict|None <- when not created
    def _safe_leaf_placement(self,
                             level: int,
                             filter_id,
                             custom_object: Optional[MutableMapping] = None):
        if custom_object is None:
            custom_object = {}
        
        new_ = False
        # Is level exists?
        if level not in self._filters:
            self._filters[level] = {}
            new_ = True

        # Is 'type' index exists?
        if new_ or type(filter_id) not in self._filters[level]:
            self._filters[level][type(filter_id)] = {}
            new_ = True

        # Placement
        # Is 'object' index exists?
        if new_ or filter_id not in self._filters[level][type(filter_id)]:
            self._filters[level][type(filter_id)][filter_id] = custom_object

        if videorotate_constants.DEBUG:
            import sys
            print('NEW_PLCMENT', level, filter_id, custom_object, new_)
            sys.stdout.flush()

        return self._filters[level][type(filter_id)][filter_id]

    def __repr__(self) -> str:
        return self.__class__.__name__ + '<' + repr(self._filters) + '>'


if __name__ == "__main__":
    logic = FilterBlockLogic()

    root_dict = logic.add_filter('root')
    root_dict['name'] = 'Gyoker'

    print('Keresd meg a "gyoker" elemet: ',
          logic.list_matching_filters({'name': 'Gyoker'}))

    kozepsoA_dict = logic.add_filter("KozepsoA", 'root')
    kozepsoA_dict['name'] = 'KozepsoA'

    print()
    print()
    print('A ... nevvel rendelkezo elemek: ',
          logic.list_matching_filters({'name': 'KozepsoA'}))
    print()
    print(logic._filters)

    kozepsoB_dict = logic.add_filter("KozepsoB", 'root')
    kozepsoB_dict['name'] = 'KozepsoB'

    print()
    print()
    print('A ... nevvel rendelkezo elemek: ',
          logic.list_matching_filters({'name': 'KozepsoB'}))
    print()
    print(logic._filters)

    print(kozepsoB_dict)
    logic.delete_filter(kozepsoB_dict['filter_id'])

    levelA_dict = logic.add_filter("levelA", 'KozepsoA')
    levelA_dict['name'] = 'levelA'

    print()
    print()
    print('A ... nevvel rendelkezo elemek: ',
          logic.list_matching_filters({'name': 'levelA'}))
    print()
    print(logic._filters)
