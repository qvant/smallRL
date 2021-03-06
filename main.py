import libtcodpy as libtcod
import math
import textwrap 
import shelve
import anydbm 
import dbhash 
import time
import os

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

MAP_WIDTH = 80
MAP_HEIGHT = 43

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

PARALIZE_RANGE = 8
PARALIZE_NUM_TURNS = 5

INVENTORY_WIDTH = 50 

#sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

#The constants that define the message bar's position and size are: 
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

MAX_INVENTORY_ITEMS = 26

MAX_OPTIONS = MAX_INVENTORY_ITEMS

HEAL_AMOUNT = 40 
LIGHTNING_DAMAGE = 40 
LIGHTNING_RANGE = 5
LIGHTNING_JUMPS = 5
LIGHTNING_JUMP_DMG_REDUCE = 2

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
CONFUSE_CLOUD_RANGE = 8

FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

FIREBOLT_RANGE = 5
FIREBOLT_DAMAGE = 50

POISON_DAMAGE = 2

BOW_RANGE = 5

#experience and level-ups
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

class casterMonster:
	def take_turn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			message( 'The ' + self.owner.name + ' growls!')
			#move towards player if far away
			if monster.distance_to(player) >= FIREBOLT_RANGE:
				monster.move_astar(player)
			elif monster.distance_to(player) >= 2: 
				cast_fireboltAI()
			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)

class rangedMonster:
	def take_turn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			message( 'The ' + self.owner.name + ' growls!')
			#move towards player if far away
			if monster.distance_to(player) >= BOW_RANGE:
				monster.move_astar(player)
			elif monster.distance_to(player) <= 2: 
				monster.fighter.attack(player)
			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				monster.move_away(player)

class ConfusedMonster:
	#AI for a temporarily confused monster (reverts to previous AI after a while).
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns
	def take_turn(self):
		if self.num_turns > 0:  #still confused...
			#move in a random direction, and decrease the number of turns confused
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1
		
		else:  #restore the previous AI (this one will be deleted because it's not referenced anymore)
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)

class ParalizedMonster:
	#AI for a temporarily confused monster (reverts to previous AI after a while).
	def __init__(self, old_ai, num_turns=PARALIZE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns
	def take_turn(self):
		if self.num_turns > 0:  #still paralized...
			pass
			self.num_turns -= 1
		
		else:  #restore the previous AI (this one will be deleted because it's not referenced anymore)
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer paralized!', libtcod.red)
			
class Equipment:
	#an object that can be equipped, yielding bonuses. automatically adds the Item component.
	def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0, add_attacks = 0, perks = []):
		self.slot = slot
		self.is_equipped = False
		self.power_bonus = power_bonus
		self.defense_bonus = defense_bonus
		self.max_hp_bonus = max_hp_bonus
		self.add_attacks = add_attacks
		self.perks = perks
		
	def toggle_equip(self):  #toggle equip/dequip status
		if self.is_equipped:
			self.dequip()
		else:
			self.equip()
	
	def equip(self):
		old_equipment = get_equipped_in_slot(self.slot)
		#equip object and show a message about it
		self.is_equipped = True
		message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)
		#if the slot is already being used, dequip whatever is there first
		if old_equipment is not None:
			old_equipment.dequip()
	
	def dequip(self):
		#dequip object and show a message about it
		if not self.is_equipped: return
		self.is_equipped = False
		message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)
		
class Item:
	#an item that can be picked up and used.
	def __init__(self, use_function = None):
		self.use_function = use_function
	def pick_up(self):
		#add to the player's inventory and remove from the map
		if len(inventory) >= MAX_INVENTORY_ITEMS:
			message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)
		#special case: automatically equip, if the corresponding equipment slot is unused
		equipment = self.owner.equipment
		if equipment and get_equipped_in_slot(equipment.slot) is None:
			equipment.equip()
	def use(self):
		#special case: if the object has the Equipment component, the "use" action is to equip/dequip
		if self.owner.equipment:
			self.owner.equipment.toggle_equip()
			return
		#just call the "use_function" if it is defined
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used.')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner)  #destroy after use, unless it was cancelled for some reason
	def drop(self):
		#add to the map and remove from the player's inventory. also, place it at the player's coordinates
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
		#special case: if the object has the Equipment component, dequip it before dropping
		if self.owner.equipment:
			self.owner.equipment.dequip()
			
class Rect:
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.x2 = x + w
		self.y1 = y
		self.y2 = y + h
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)
	def intersect(self, other):
		# return true if rectanges intersected
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

def create_room(room):
	global map
	#go through the tiles in the rectangle and make them passable
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False
			
def create_h_tunnel(x1, x2, y):
	global map
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
def create_v_tunnel(y1, y2, x):
	global map
	#vertical tunnel
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def get_names_under_mouse():
	global mouse
	
	#return a string with the names of all objects under the mouse
	(x, y) = (mouse.cx, mouse.cy)
	#create a list with the names of all objects at the mouse's coordinates and in FOV
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	names = ', '.join(names)  #join the names, separated by commas
	return names.capitalize()
		
def handle_keys():
	global playerx, playery, fov_recompute, key
	
	#key = libtcod.console_check_for_keypress()  #real-time
	#key = libtcod.console_wait_for_keypress(True)  #turn-based

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit'  #exit game
	
	if game_state == 'playing':
		#movement keys
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			player_move_or_attack(0, -1)

		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			player_move_or_attack(0, 1)
	 
		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			player_move_or_attack(-1, 0)

		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			player_move_or_attack(1, 0)
		
		elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
			player_move_or_attack(-1, -1)
			
		elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
			player_move_or_attack(1, -1)
			
		elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
			player_move_or_attack(-1, 1)
			
		elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
			player_move_or_attack(1, 1)
		
		elif key.vk == libtcod.KEY_KP5:
			pass  #do nothing ie wait for the monster to come to you
		else:
			#test for other keys
			key_char = chr(key.c)
			
			if key_char == 'g':
				#pick up an item
				for object in objects:  #look for an item in the player's tile
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
			elif key_char == 'i':
				#show the inventory
				chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()
			elif key_char == 'd':
				#show the inventory; if an item is selected, drop it
				chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()
			elif key_char == '<':
				#go down stairs, if the player is on them
				if stairs.x == player.x and stairs.y == player.y:
					next_level()
			elif key_char == 'c':
				#show character information
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
                    '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)
			#time.sleep(0.1)
			return 'didnt-take-turn'

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on screen.
	def __init__(self, x, y, char, color, name = '', blocks = False, fighter = None, ai = None, item = None, always_visible=False, equipment=None, stats=None):
		self.x = x
		self.y = y
		self.char = char
		self.color = color
		self.name = name
		self.blocks = blocks
		self.fighter = fighter
		if self.fighter:
			#let the fighter component know who owns it
			self.fighter.owner = self
			
		self.ai = ai
		if self.ai:
			#let the ai component know who owns it
			self.ai.owner = self
		self.item = item
		if self.item:
			self.item.owner = self
		self.always_visible = always_visible
		self.equipment = equipment
		if self.equipment:  #let the Equipment component know who owns it
			self.equipment.owner = self
			self.item = Item()
			self.item.owner = self
		self.stats = stats
 
	def move(self, dx, dy):
		#move by the given amount
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
 
	def draw(self):
		#only show if it's visible to the player; or it's set to "always visible" and on an explored tile
		#print(self.always_visible)
		if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or
            (self.always_visible and map[self.x][self.y].explored)):
			#set the color and then draw the character that represents this object at its position
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
 
	def clear(self):
		#erase the character that represents this object
		if not(old_map_style):
			libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
		#else:
		#	if map[self.x][self.y].block_sight:
		#		libtcod.console_put_char_ex(con, self.x, self.y, '.', libtcod.white, black.black)
	
	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)

		#normalize it to length 1 (preserving direction), then round it and
		#convert to integer so the movement is restricted to the map grid
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)
		
	def distance_to(self, other):
		#return the distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)
		
	def send_to_back(self):
		#make this object be drawn first, so all others appear above it if they're in the same tile.
		global objects
		objects.remove(self)
		objects.insert(0, self)
	def distance(self, x, y):
		#return the distance to some coordinates
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
		
	def move_astar(self, target):
		#Create a FOV map that has the dimensions of the map
		fov = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
		
		#Scan the current map each turn and set all the walls as unwalkable
		for y1 in range(MAP_HEIGHT):
			for x1 in range(MAP_WIDTH):
				libtcod.map_set_properties(fov, x1, y1, not map[x1][y1].block_sight, not map[x1][y1].blocked)
		
		#Scan all the objects to see if there are objects that must be navigated around
		#Check also that the object isn't self or the target (so that the start and the end points are free)
		#The AI class handles the situation if self is next to the target so it will not use this A* function anyway   
		for obj in objects:
			if obj.blocks and obj != self and obj != target:
				#Set the tile as a wall so it must be navigated around
				libtcod.map_set_properties(fov, obj.x, obj.y, True, False)
		
		#Allocate a A* path
		#The 1.41 is the normal diagonal cost of moving, it can be set as 0.0 if diagonal moves are prohibited
		my_path = libtcod.path_new_using_map(fov, 1.41)
		
		#Compute the path between self's coordinates and the target's coordinates
		libtcod.path_compute(my_path, self.x, self.y, target.x, target.y)
		
		#Check if the path exists, and in this case, also the path is shorter than 25 tiles
		#The path size matters if you want the monster to use alternative longer paths (for example through other rooms) if for example the player is in a corridor
		#It makes sense to keep path size relatively low to keep the monsters from running around the map if there's an alternative path really far away        
		if not libtcod.path_is_empty(my_path) and libtcod.path_size(my_path) < 25:
			#Find the next coordinates in the computed full path
			x, y = libtcod.path_walk(my_path, True)
			if x or y:
				#Set self's coordinates to the next path tile
				self.x = x
				self.y = y
		else:
			#Keep the old move function as a backup so that if there are no paths (for example another monster blocks a corridor)
			#it will still try to move towards the player (closer to the corridor opening)
			self.move_towards(target.x, target.y)  
		
		#Delete the path to free memory
		libtcod.path_delete(my_path)
		
	def move_away(self, target):
		if target.x > self.x:
			x = -1
		elif target.x > self.x:
			x = 1
		else:
			x = 0
		if target.y > self.y:
			y = -1
		elif target.u > self.u:
			y = 1
		else:
			y = 0
		if is_blocked(self.x + x, self.y + y ):
			x = 0
		if is_blocked(self.x + x, self.y + y ):
			y = 0
		self.move(x, y)  
		
		#Delete the path to free memory
		libtcod.path_delete(my_path)
		
class Tile:
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None:
			block_sight = blocked
		self.block_sight = block_sight
		self.explored = False
		
class Fighter:
	#combat-related properties and methods (monster, player, NPC).
	def __init__(self, hp, defense, power, xp, death_function=None, attacks = 1, perks = [], spells = []):
		self.base_max_hp = hp
		self.hp = hp
		self.base_defense = defense
		self.base_power = power
		self.death_function = death_function
		self.xp = xp
		self.base_attacks = attacks
		self.base_perks = perks
		self.base_spells = spells
	
	@property
	def power(self):
		bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
		return self.base_power + bonus
	@property
	def defense(self):  #return actual defense, by summing up the bonuses from all equipped items
		bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
		return self.base_defense + bonus
	
	@property
	def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
		bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_hp + bonus
	@property
	def attack_num(self):
		bonus = sum(equipment.add_attacks for equipment in get_all_equipped(self.owner))
		return self.base_attacks + bonus
	
	@property
	def perks(self):
		perks = []
		for i in get_all_equipped(self.owner):
			perks += i.perks
		return perks + self.base_perks
	@property
	def spells(self):
		return self.base_spells
		
	def take_damage(self, damage):
		#apply damage if possible
		if damage > 0:
			self.hp -= damage
		if self.owner != player:
			player.stats.recive_dmg(damage)
		else:
			player.stats.inflict_dmg(damage)
		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				function(self.owner)
			if show_corpses:
				self.owner.always_visible = True
			if self.owner != player:  #yield experience to the player
				player.fighter.xp += self.xp
				player.stats.kill_monster()
	def attack(self, target):
		#a simple formula for attack damage
		if not ('phase' in self.perks):
			damage = self.power - target.fighter.defense
		else:
			damage = self.power
		
		for i in range(self.attack_num):
			if damage > 0 and target.fighter is not None:
				#make the target take some damage
				message( self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
				target.fighter.take_damage(damage)
			elif target.fighter is not None:
				message (self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')
			if 'poison' in self.perks:
				target.fighter.base_perks.append('poisoned')
	def heal(self, amount):
		#heal by the given amount, without going over the maximum
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp

		
class BasicMonster:
	#AI for a basic monster.
	def take_turn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			message( 'The ' + self.owner.name + ' growls!')
			#move towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_astar(player)
			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)
				
class Stats:
	def __init__(self, name = None):
		self.steps = 0
		self.dmg_recived = 0
		self.dmg_inflicted = 0
		self.scrolls_used = 0
		self.potions_used = 0
		self.monster_killed = 0
	def make_step(self):
		self.steps += 1
	def recive_dmg(self, dmg):
		self.dmg_recived += dmg
	def inflict_dmg(self, dmg):
		self.dmg_inflicted += dmg
	def used_scroll(self):
		self.scrolls_used += 1
	def use_potion(self):
		self.potions_used += 1
	def kill_monster(self):
		self.monster_killed += 1
		
def place_objects(room):
	#maximum number of monsters per room
	max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])
	
	#chance of each monster
	monster_chances = {}
	monster_chances['orc'] = 80  #orc always shows up, even if all other monsters have 0 chance
	monster_chances['troll'] = from_dungeon_level([[15, 3], [30, 5], [60, 7], [30, 9]])
	monster_chances['shadow'] = from_dungeon_level([[20, 5], [60, 7]])
	monster_chances['snake'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])
	monster_chances['orc archer'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])
	monster_chances['lich'] = from_dungeon_level([[30, 5], [40, 7]])
	monster_chances['dragon'] = from_dungeon_level([ [20, 9], [30, 12]])
	
	#maximum number of items per room
	max_items = from_dungeon_level([[1, 1], [2, 4]])
	
	#chance of each item (by default they have a chance of 0 at level 1, which then goes up)
	item_chances = {}
	item_chances['heal'] = 35  #healing potion always shows up, even if all other items have 0 chance
	item_chances['lightning'] = from_dungeon_level([[25, 4]])
	item_chances['chain lightning'] = from_dungeon_level([[10, 4]])
	item_chances['fireball'] =  from_dungeon_level([[25, 6]])
	item_chances['firebolt'] =  from_dungeon_level([[25, 6]])
	item_chances['confuse cloud'] =  from_dungeon_level([[5, 6]])
	item_chances['confuse'] =   from_dungeon_level([[10, 2]])
	item_chances['paralize'] =   from_dungeon_level([[10, 2]])
	item_chances['teleport'] =   from_dungeon_level([[10, 2]])
	item_chances['sword'] =     from_dungeon_level([[5, 4]])
	item_chances['holy sword'] =     from_dungeon_level([[7, 4]])
	item_chances['fire sword'] =     from_dungeon_level([[7, 4]])
	item_chances['mastercrafted_dagger'] =     from_dungeon_level([[5, 4]])
	item_chances['poisoned dagger'] =     from_dungeon_level([[5, 4]])
	item_chances['phase_dagger'] =     from_dungeon_level([[7, 4]])
	item_chances['shield'] =    from_dungeon_level([[15, 8]])
	item_chances['leather helm'] =    from_dungeon_level([[15, 2]])
	item_chances['skullcap'] =    from_dungeon_level([[10, 46]])
	item_chances['bascinet'] =    from_dungeon_level([[5, 12]])
	item_chances['leather jacket'] =    from_dungeon_level([[15, 3]])
	item_chances['chain mail'] =    from_dungeon_level([[10, 9]])
	item_chances['full plate'] =    from_dungeon_level([[5, 14]])
	
	#item_chances = {'heal': 70, 'lightning': 10, 'fireball': 10, 'confuse': 10}
	#place monsters
	#choose random number of monsters
	num_monsters = libtcod.random_get_int(0, 0, max_monsters)
	
	for i in range(num_monsters):
		#choose random spot for this monster
		x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
		y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
		
		if not is_blocked(x, y):
			
			choice = random_choice(monster_chances)
			if choice == 'orc':  
				#create an orc
				fighter_component = Fighter(hp=20, defense=0, power=4, death_function=monster_death, xp = 35)
				ai_component = BasicMonster()
				monster = Object(x, y, 'o', libtcod.desaturated_green, 'orc', True, fighter_component, ai_component)
			elif choice == 'troll':
				#create a troll
				fighter_component = Fighter(hp=30, defense=2, power=8, death_function=monster_death, xp = 100)
				ai_component = BasicMonster()
				monster = Object(x, y, 'T', libtcod.darker_green, 'troll', True, fighter_component, ai_component)
			elif choice == 'shadow':
				fighter_component = Fighter(hp=50, defense=10, power=8, death_function=monster_death, xp = 200, perks = ['phase'])
				ai_component = BasicMonster()
				monster = Object(x, y, 's', libtcod.darker_blue, 'shadow', True, fighter_component, ai_component)
			elif choice == 'snake':
				fighter_component = Fighter(hp=70, defense=1, power=3, death_function=monster_death, xp = 200, attacks = 2, perks = ['poison'])
				ai_component = BasicMonster()
				monster = Object(x, y, 's', libtcod.darker_yellow, 'snake', True, fighter_component, ai_component)
			elif choice == 'lich':
				fighter_component = Fighter(hp=70, defense=6, power=8, death_function=monster_death, xp = 400, attacks = 1)
				ai_component = casterMonster()
				monster = Object(x, y, 's', libtcod.lighter_red, 'lich', True, fighter_component, ai_component)
			elif choice == 'orc archer':
				fighter_component = Fighter(hp=20, defense=0, power=5, death_function=monster_death, xp = 400, attacks = 1)
				ai_component = rangedMonster()
				monster = Object(x, y, 's', libtcod.desaturated_green, 'orc archer', True, fighter_component, ai_component)
			elif choice == 'dragon':
				fighter_component = Fighter(hp=200, defense=8, power=10, death_function=monster_death, xp = 400, attacks = 1)
				ai_component = basicMonster()
				monster = Object(x, y, 's', libtcod.darker_red, 'dragon', True, fighter_component, ai_component)
				
			objects.append(monster)
	#place items
	num_items = libtcod.random_get_int(0, 0, max_items)
	
	for i in range(num_items):
		#choose random spot for this item
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			choice = random_choice(item_chances)
			if choice == 'heal':
				#create a healing potion
				item_component = Item(use_function=cast_heal)
				item = Object(x, y, '!', name = 'healing potion', color = libtcod.violet, item=item_component, always_visible=True)
			elif choice == 'lightning':
				#create a lightning bolt scroll (10% chance)
				item_component = Item(use_function=cast_lightning)
				
				item = Object(x, y, '#', name = 'scroll of lightning bolt', color = libtcod.light_yellow, item=item_component, always_visible=True)
			elif choice == 'chain lightning':
				#create a chain lightning bolt scroll 
				item_component = Item(use_function=cast_chain_lightning)
				
				item = Object(x, y, '#', name = 'scroll of chain lightning', color = libtcod.light_green, item=item_component, always_visible=True)
			elif choice == 'fireball':
				#create a fireball scroll (10% chance)
				item_component = Item(use_function=cast_fireball)
				
				item = Object(x, y, '#', name = 'scroll of fireball', color = libtcod.light_yellow, item=item_component, always_visible=True)
			elif choice == 'firebolt':
				#create a fireball scroll (10% chance)
				item_component = Item(use_function=cast_firebolt)
				
				item = Object(x, y, '#', name = 'scroll of fireball', color = libtcod.light_yellow, item=item_component, always_visible=True)
			elif choice == 'confuse':
				#create a lightning bolt scroll (10% chance)
				item_component = Item(use_function=cast_confuse)
				item = Object(x, y, '#', name = 'scroll of confuse', color = libtcod.light_yellow, item=item_component, always_visible=True)
			elif choice == 'confuse cloud':
				item_component = Item(use_function=cast_confuse_cloud)
				item_component = Item(use_function=cast_confuse_cloud)
				item = Object(x, y, '#', name = 'scroll of confuse cloud', color = libtcod.light_yellow, item=item_component, always_visible=True)
			elif choice == 'paralize':
				item_component = Item(use_function=cast_paralize)
				item = Object(x, y, '#', name = 'scroll of paralize', color = libtcod.light_yellow, item=item_component, always_visible=True)
			elif choice == 'teleport':
				item_component = Item(use_function=cast_teleport)
				item = Object(x, y, '#', name = 'scroll of teleport', color = libtcod.light_yellow, item=item_component, always_visible=True)
			elif choice == 'sword':
				#create a sword
				equipment_component = Equipment(slot='right hand', power_bonus = 3)
				item = Object(x, y, '/', name = 'sword', color = libtcod.sky, equipment=equipment_component)
			elif choice == 'holy sword':
				equipment_component = Equipment(slot='right hand', power_bonus = 10)
				item = Object(x, y, '/', name = 'holy sword', color = libtcod.sky, equipment=equipment_component)
			elif choice == 'fire sword':
				#create a sword
				equipment_component = Equipment(slot='right hand', power_bonus = 9)
				item = Object(x, y, '/', name = 'fire sword', color = libtcod.sky, equipment=equipment_component)
			elif choice == 'mastercrafted_dagger':
				#create a sword
				equipment_component = Equipment(slot='right hand', power_bonus = 2, add_attacks = 2)
				item = Object(x, y, '/', name = 'mastercrafted_dagger', color = libtcod.sky, equipment=equipment_component)
			elif choice == 'poisoned dagger':
				#create a sword
				equipment_component = Equipment(slot='right hand', power_bonus = 2, add_attacks = 2, perks = 'poison')
				item = Object(x, y, '/', name = 'poisoned dagger', color = libtcod.sky, equipment=equipment_component)
			elif choice == 'phase_dagger':
				#create a sword
				equipment_component = Equipment(slot='right hand', power_bonus = 3, add_attacks = 3, perks = ['phase'])
				item = Object(x, y, '/', name = 'phase_dagger', color = libtcod.sky, equipment=equipment_component)
			elif choice == 'shield':
				#create a shield
				equipment_component = Equipment(slot='left hand', defense_bonus=1)
				item = Object(x, y, '[', name = 'shield', color = libtcod.darker_orange, equipment=equipment_component)
			elif choice == 'leather helm':
				#create a leather helm
				equipment_component = Equipment(slot='head', defense_bonus=1)
				item = Object(x, y, '[', name = 'leather helm', color = libtcod.darker_orange, equipment=equipment_component)
			elif choice == 'skullcap':
				#create a skullcap
				equipment_component = Equipment(slot='head', defense_bonus=2)
				item = Object(x, y, '[', name = 'skullcap', color = libtcod.darker_orange, equipment=equipment_component)
			elif choice == 'bascinet':
				#create a bascinet
				equipment_component = Equipment(slot='head', defense_bonus=3)
				item = Object(x, y, '[', name = 'bascinet', color = libtcod.darker_orange, equipment=equipment_component)
			elif choice == 'leather jacket':
				#create a leather jacket
				equipment_component = Equipment(slot='breast', defense_bonus=1)
				item = Object(x, y, '[', name = 'leather jacket', color = libtcod.darker_orange, equipment=equipment_component)
			elif choice == 'chain mail':
				#create a chain mail
				equipment_component = Equipment(slot='breast', defense_bonus=3)
				item = Object(x, y, '[', name = 'chain mail', color = libtcod.darker_orange, equipment=equipment_component)
			elif choice == 'full plate':
				#create a full plate
				equipment_component = Equipment(slot='breast', defense_bonus=6)
				item = Object(x, y, '[', name = 'full plate', color = libtcod.darker_orange, equipment=equipment_component)
				
			
			objects.append(item)
			item.send_to_back()  #items appear below other objects
		
def cast_lightning():
	#find closest enemy (inside a maximum range) and damage it
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:  #no enemy found within maximum range
		message('No enemy is close enough to strike.', libtcod.red)
		return 'cancelled'
	
	#zap it!
	message('A lighting bolt strikes the ' + monster.name + ' with a loud thunder! The damage is '
        + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)
	player.stats.use_scroll()
	
def cast_firebolt():
	#find closest enemy (inside a maximum range) and damage it
	message('Left-click a target tile for the firebolt, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	
	#zap it!
	message('A bolt of fire strikes the ' + monster.name + ' with a loud thunder! The damage is '
        + str(FIREBOLT_DAMAGE) + ' hit points.', libtcod.orange)
	monster.fighter.take_damage(FIREBOLT_DAMAGE)
	player.stats.use_scroll()	
	
def cast_fireboltAI():
	message('A bolt of fire strikes you with a loud thunder! The damage is '
        + str(FIREBOLT_DAMAGE) + ' hit points.', libtcod.orange)
	player.fighter.take_damage(FIREBOLT_DAMAGE)		
	
def cast_chain_lightning():
	#find closest enemy (inside a maximum range) and damage it
	exclude = [player]
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:  #no enemy found within maximum range
		message('No enemy is close enough to strike.', libtcod.red)
		return 'cancelled'
	
	#zap it!
	for i in range(LIGHTNING_JUMPS):
		message('A chain lighting strikes the ' + monster.name + ' with a loud thunder! The damage is '
        + str(LIGHTNING_DAMAGE - i * LIGHTNING_JUMP_DMG_REDUCE) + ' hit points.', libtcod.light_blue)
		monster.fighter.take_damage(LIGHTNING_DAMAGE - i * LIGHTNING_JUMP_DMG_REDUCE)
		monster = closest_monster(LIGHTNING_RANGE, monster, exclude)
		if monster is None:
			break
		exclude.append(monster)
	player.stats.use_scroll()
		
	
def cast_confuse():
	message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None: return 'cancelled'
	#replace the monster's AI with a "confused" one; after some turns it will restore the old AI
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster  #tell the new component who owns it
	message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)	
	player.stats.use_scroll()
	
def cast_paralize():
	message('Left-click an enemy to paralize it, or right-click to cancel.', libtcod.light_cyan)
	monster = target_monster(PARALIZE_RANGE)
	if monster is None: return 'cancelled'
	#replace the monster's AI with a "confused" one; after some turns it will restore the old AI
	old_ai = monster.ai
	monster.ai = ParalizedMonster(old_ai)
	monster.ai.owner = monster  #tell the new component who owns it
	message('The eyes of the ' + monster.name + ' look black and mindless!', libtcod.light_green)	
	player.stats.use_scroll()
	
def cast_teleport():
	global fov_recompute
	while True:
		x = libtcod.random_get_int(0, MAP_WIDTH,  MAP_WIDTH / 2)
		y = libtcod.random_get_int(0, MAP_HEIGHT, MAP_HEIGHT / 2)
		if not is_blocked(x, y):
			break
	player.x = x
	player.y = y
	fov_recompute = True
	message('You sudden appear in another place!', libtcod.light_green)	
	player.stats.use_scroll()
	
def cast_confuse_cloud():
	message('Left-click a target tile for the confuse cloud, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	for obj in objects:  #damage every fighter in range, including the player
		if obj.distance(x, y) <= CONFUSE_CLOUD_RANGE and obj.fighter and obj != player:
			#replace the monster's AI with a "confused" one; after some turns it will restore the old AI
			old_ai = obj.ai
			obj.ai = ConfusedMonster(old_ai)
			obj.ai.owner = obj  #tell the new component who owns it
			message('The eyes of the ' + obj.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)
	player.stats.use_scroll()
	

def cast_fireball():
	#ask the player for a target tile to throw a fireball at
	message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
	
	for obj in objects:  #damage every fighter in range, including the player
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)
	player.stats.use_scroll()

			
def closest_monster(max_range, target = None, exclude = []):
	#find closest enemy, up to a maximum range, and in the target's FOV
	if target is None:
		target = player
	closest_enemy = None
	closest_dist = max_range + 1  #start with (slightly more than) maximum range
	
	for object in objects:
		if object.fighter and not object == target and libtcod.map_is_in_fov(fov_map, object.x, object.y) and object not in exclude:
			#calculate distance between this object and the player
			dist = target.distance_to(object)
			if dist < closest_dist:  #it's closer, so remember it
				closest_enemy = object
				closest_dist = dist
	return closest_enemy

def target_monster(max_range=None):
	#returns a clicked monster inside FOV up to a range, or None if right-clicked
	while True:
		(x, y) = target_tile(max_range)
		if x is None:  #player cancelled
			return None
		
		#return the first clicked monster, otherwise continue looping
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj
	
def target_tile(max_range=None):
	#return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
	global key, mouse
	while True:
		#render the screen. this erases the inventory and shows the names of objects under the mouse.
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
		render_all()
		
		(x, y) = (mouse.cx, mouse.cy)
		
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
            (max_range is None or player.distance(x, y) <= max_range)):
			return (x, y)
		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return (None, None)  #cancel if the player right-clicked or pressed Escape
		
def is_blocked(x, y):
	#first test the map tile
	if map[x][y].blocked:
		return True
		
	#now check for any blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True

	return False

def player_move_or_attack(dx, dy):
	global fov_recompute
	
	#the coordinates the player is moving to/attacking
	x = player.x + dx 
	y = player.y + dy
	#try to find an attackable object there
	target = None
	for object in objects:
		if object.x == x and object.y == y and object.fighter:
			target = object
			break
	
	#attack if target found, move otherwise
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True
		player.stats.make_step
	#time.sleep(0.1)
	
def make_map():
	global map, objects, stairs, dungeon_level
	
	#the list of objects with just the player
	player.x = 25
	player.y = 23
	objects = [player]
	#fill map with "unblocked" tiles
	map = [[Tile(True)
		for y in range(MAP_HEIGHT)]
			for i in range(MAP_WIDTH)]
	#room1 = Rect(20, 15, 10, 15)
	#room2 = Rect(50, 15, 10, 15)
	#create_room(room1)
	#create_room(room2)
	#create_h_tunnel(25, 55, 23)
	rooms = []
	num_rooms = 0
	for i in range(MAX_ROOMS):
		width = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		height = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - width - 1 )
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - height - 1 )
		
		#"Rect" class makes rectangles easier to work with
		new_room = Rect(x, y, width, height)
		#run through the other rooms and see if they intersect with this one
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
		if not failed:
			#this means there are no intersections, so this room is valid
			
			#"paint" it to the map's tiles
			create_room(new_room)
			
			#center coordinates of new room, will be useful later
			(new_x, new_y) = new_room.center()
			
			if num_rooms == 0:
				#this is the first room, where the player starts at
				player.x = new_x
				player.y = new_y
			else:
				#all rooms after the first:
				#connect it to the previous room with a tunnel
				
				#center coordinates of previous room
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				
				#draw a coin (random number that is either 0 or 1)
				if libtcod.random_get_int(0, 0, 1) == 1:
					#first move horizontally, then vertically
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					#first move vertically, then horizontally
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
				#firsr room always safe
				#add some contents to this room, such as monsters
				place_objects(new_room)
 
			#finally, append the new room to the list
			rooms.append(new_room)
			num_rooms += 1
			#room_no = Object(new_x, new_y, chr(65+num_rooms), libtcod.white, 'room number')
			#objects.insert(0, room_no) #draw early, so monsters are drawn on top
	#create stairs at the center of the last room
	stairs = Object(new_x, new_y, '<', name='stairs', color=libtcod.white, always_visible=True)
	objects.append(stairs)
	stairs.send_to_back()  #so it's drawn below the monsters
	
	
def player_death(player):
	#the game ended!
	global game_state
	message( 'You died!', libtcod.red)
	game_state = 'dead'
	
	#for added effect, transform the player into a corpse!
	player.char = '%'
	player.color = libtcod.dark_red
	
	window = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
	
	#print the header, with auto-wrap
	libtcod.console_set_default_background(window, libtcod.green)
	libtcod.console_set_default_foreground(window, libtcod.yellow)
	dump_text = "You died! \n" + "You was level " + str(player.level) + "\n You achieved " + str(dungeon_level) + " with " + str(player.fighter.max_hp) + " hp " 
	dump_text += "\n " + str(player.fighter.base_power) + " strength "
	dump_text += "\n " + str(player.fighter.base_defense) + " agility "
	dump_text += "\n You made: " + str(player.stats.steps) + " steps "
	dump_text += "\n You used: " + str(player.stats.scrolls_used) + " scrolls "
	dump_text += "\n You used: " + str(player.stats.potions_used) + " potions "
	dump_text += "\n You recieved: " + str(player.stats.dmg_recived) + " damage "
	dump_text += "\n You inflicted: " + str(player.stats.dmg_inflicted) + " damage "
	dump_text += "\n You killed: " + str(player.stats.monster_killed) + " monsters "
	dump_text += "\n You had: "
	for obj in inventory:
		dump_text += "\n " + obj.name
	dump_text += "\n And it was completely useless"
	dump_msg  = dump_text + "\n Press a to make character dump and any other key to close stat screen"
	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 
	y = SCREEN_HEIGHT/2
	libtcod.console_print_ex(window, 0, 0, libtcod.BKGND_NONE, libtcod.LEFT, dump_msg)
	
	 
	# 0.7 background transparacy
	libtcod.console_blit(window, 0, 0, x, y, 0, x, y, 1.0, 0.7)
	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	key_char = chr(key.c)
	if key_char == 'a':
		filename = "dumps/"+ str(player.name)+".cdp"
		dir = os.path.dirname(filename)
		if not os.path.exists(dir):
			os.makedirs(dir)
		f = open(filename, 'w')
		f.write(dump_text)
		f.close()
 
def monster_death(monster):
	#transform it into a nasty corpse! it doesn't block, can't be
	#attacked and doesn't move
	message( monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()
	
def render_all():
	global color_light_wall
	global color_light_ground
	global fov_recompute
	global game_msgs
	
	if fov_recompute:
		#recompute FOV if needed (the player moved or something)
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			wall = map[x][y].block_sight
			visible = libtcod.map_is_in_fov(fov_map, x, y)
			if not(visible):
				#if it's not visible right now, the player can only see it if it's explored
				if map[x][y].explored:
					#it's out of the player's FOV
					if wall:
						if not(old_map_style):
							libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET )
						else:
							libtcod.console_put_char_ex(con, x, y, '#', libtcod.grey, libtcod.black)
					else:
						if not(old_map_style):
							libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET )
						else:
							libtcod.console_put_char_ex(con, x, y, '.', libtcod.grey, libtcod.black)
			else:
				if wall:
					if not(old_map_style):
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
					else:
						libtcod.console_put_char_ex(con, x, y, '#', libtcod.white, libtcod.black)
				else:
					if not(old_map_style):
						libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
					else:
						libtcod.console_put_char_ex(con, x, y, '.', libtcod.white, libtcod.black)
				map[x][y].explored = True
	#draw all objects in the list, except the player. we want it to
	#always appear over all other objects! so it's drawn later.
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
	libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
	#show the player's stats
	#libtcod.console_set_default_foreground(con, libtcod.white)
	#libtcod.console_print_ex(0, 1, SCREEN_HEIGHT - 2, libtcod.BKGND_NONE, libtcod.LEFT,
    #    'HP: ' + str(player.fighter.hp) + '/' + str(player.fighter.max_hp))
	#prepare to render the GUI panel
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
 
	#show the player's stats
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
        libtcod.light_red, libtcod.darker_red)
	libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level ' + str(dungeon_level))
	
	#display names of objects under the mouse
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
	
	#print the game messages, one line at a time
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
    #blit the contents of "panel" to the root console
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
	
		
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#render a bar (HP, experience, etc). first calculate the width of the bar
	bar_width = int(float(value) / maximum * total_width)
	
	#render the background first
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
	
	#now render the bar on top
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
	#finally, some centered text with the values
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
        name + ': ' + str(value) + '/' + str(maximum))
	
	
def message(new_msg, color = libtcod.white):
	global game_msgs
	#split the message if necessary, among multiple lines
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
	for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room for the new one
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
		#add the new line as a tuple, with the text and the color
		game_msgs.append((line, color))
	

def menu(header, options, width):
	if len(options) > MAX_OPTIONS: raise ValueError('Cannot have a menu with more than 26 options.')
	#calculate total height for the header (after auto-wrap) and one line per option
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height
	#create an off-screen console that represents the menu's window
	window = libtcod.console_new(width, height)
	
	#print the header, with auto-wrap
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letter_index += 1
	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	# 0.7 background transparacy
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	while True:
		key = libtcod.console_wait_for_keypress(True)
		if key.vk == libtcod.KEY_ENTER and key.lalt:  #(special case) Alt+Enter: toggle fullscreen
			libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		else:
			break
	#convert the ASCII code to an index; if it corresponds to an option, return it
	index = key.c - ord('a')
	time.sleep(0.3)
	if index >= 0 and index < len(options): return index
	return None

def inventory_menu(header):
	#show a menu with each item of the inventory as an option
	if len(inventory) == 0:
		options = ['Inventory is empty.']
	else:
		options = [item.name for item in inventory]
	
	index = menu(header, options, INVENTORY_WIDTH)
	#if an item was chosen, return it
	if index is None or len(inventory) == 0: return None
	return inventory[index].item
	
def cast_heal():
	#heal the player
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.', libtcod.red)
		return 'cancelled'

	message('Your wounds start to feel better!', libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)
	player.stats.use_potion()
	
def new_game():
	global player, inventory, game_msgs, game_state, dungeon_level
	fighter_component = Fighter(hp=100, defense=1, power=2, xp = 0, death_function=player_death)
	stats_component = Stats()
	player = Object(MAP_WIDTH/2, MAP_HEIGHT/2, '@', libtcod.white, 'player', blocks = True, fighter = fighter_component, stats = stats_component)
	player.level = 1
	game_state = 'playing'
	libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)
	dungeon_level = 1
	#generate map (at this point it's not drawn to the screen)
	make_map()
	#The new_game function should initialize FOV right after creating the map:
	initialize_fov()
	
	#create the list of game messages and their colors, starts empty
	game_msgs = []
	
	inventory = []

	#a warm welcoming message!
	message('Welcome stranger! Prepare to perish in the Tombs of the Ancient Kings.', libtcod.red)
	
	#initial equipment: a dagger
	equipment_component = Equipment(slot='right hand', power_bonus=2)
	obj = Object(0, 0, '-', name = 'dagger', color = libtcod.sky, equipment=equipment_component)
	inventory.append(obj)
	equipment_component.equip()
	obj.always_visible = True
	
	
	
	
def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	#create the FOV map, according to the generated map
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
			
def play_game():
	global key, mouse
	player_action = None
	
	mouse = libtcod.Mouse()
	key = libtcod.Key()

	while not libtcod.console_is_window_closed():	
		
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
		render_all()
		
		libtcod.console_flush()
		check_level_up()
		
		for object in objects:
			object.clear()
			
		#handle keys and exit game if needed
		player_action = handle_keys()
		if player_action == 'exit':
			save_game()
			break
		#let monsters take their turn
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()
				if object.fighter:
					for x in object.fighter.perks:
						if x == 'poisoned':
							object.fighter.take_damage(POISON_DAMAGE)
	#key = libtcod.console_wait_for_keypress(True)
					
def main_menu():
	img = libtcod.image_load('menu_background.png')
	
	while not libtcod.console_is_window_closed():
		#show the background image, at twice the regular console resolution
		libtcod.image_blit_2x(img, 0, 0, 0)
		
		#show the game's title, and some credits!
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,
            'TOMBS OF THE ANCIENT KINGS')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER,
            'By qvant86, special thanks to Jotaf')
		
		#show options and wait for the player's choice
		
		choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)
		
		if choice == 0:  #new game
			new_game()
			play_game()
		elif choice == 1:  #load game
			try:
				load_game()
			except:
				msgbox("No saved game to load")
				continue
			play_game()
		elif choice == 2 or choice is None:  #quit
			break
			
def save_game():
	#open a new empty shelve (possibly overwriting an old one) to write the game data
	file = shelve.open("savegame", 'n')
	file['map'] = map
	file['objects'] = objects
	file['player_index'] = objects.index(player)  #index of player in objects list
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['stairs_index'] = objects.index(stairs)
	file['dungeon_level'] = dungeon_level
	file.close()
	
def load_game():
	#open the previously saved shelve and load the game data
	global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level
	
	file = shelve.open('savegame', 'r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']]  #get index of player in objects list and access it
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	stairs = objects[file['stairs_index']]
	dungeon_level = file['dungeon_level']
	file.close()
	
	initialize_fov()
	
def msgbox(text, width=50):
	#time.sleep(0.3)
	menu(text, [], width)  #use menu() as a sort of "message box"
	#time.sleep(0.3)

def next_level():
	global dungeon_level
	#advance to the next level
	message('You take a moment to rest, and recover your strength.', libtcod.light_violet)
	player.fighter.heal(player.fighter.max_hp / 2)  #heal the player by 50%
	
	message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', libtcod.red)
	libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)
	make_map()  #create a fresh new level!
	initialize_fov()
	dungeon_level += 1
	save_game()
	
def check_level_up():
	#see if the player's experience is enough to level-up
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		#it is! level up
		player.level += 1
		player.fighter.xp -= level_up_xp
		message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)
		choice = None
		while choice == None:  #keep asking until a choice is made
			choice = menu('Level up! Choose a stat to raise:\n',
                ['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
                'Strength (+1 attack, from ' + str(player.fighter.power) + ')',
                'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)
		
		if choice == 0:
			player.fighter.base_max_hp += 20
			player.fighter.hp += 20
		elif choice == 1:
			player.fighter.base_power += 1
		elif choice == 2:
			player.fighter.base_defense += 1

def random_choice_index(chances):  #choose one option from list of chances, returning its index
	#the dice will land on some number between 1 and the sum of the chances
	dice = libtcod.random_get_int(0, 1, sum(chances))
	
	#go through all chances, keeping the sum so far
	running_sum = 0
	choice = 0
	for w in chances:
		running_sum += w
		
		#see if the dice landed in the part that corresponds to this choice
		if dice <= running_sum:
			return choice
		choice += 1
		
def random_choice(chances_dict):
	#choose one option from dictionary of chances, returning its key
	chances = chances_dict.values()
	strings = chances_dict.keys()
	return strings[random_choice_index(chances)]
	
def from_dungeon_level(table):
	global dungeon_level
	#returns a value that depends on level. the table specifies what value occurs after each level, default is 0.
	for (value, level) in reversed(sorted(table)):
		if dungeon_level >= level:
			return value
	return 0
	
def get_equipped_in_slot(slot):  #returns the equipment in a slot, or None if it's empty
	for obj in inventory:
		if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
			return obj.equipment
	return None

def get_all_equipped(obj):  #returns a list of equipped items
	if obj == player:
		equipped_list = []
		for item in inventory:
			if item.equipment and item.equipment.is_equipped:
				equipped_list.append(item.equipment)
		return equipped_list
	else:
		return []  #other objects have no equipment
	
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)

con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
#For a real-time roguelike, you wanna limit the speed of the game (frames-per-second or FPS). If you want it to be turn-based, ignore this line. (This line will simply have no effect if your game is turn-based.) 
libtcod.sys_set_fps(LIMIT_FPS)





color_dark_wall = libtcod.Color(0, 0, 100)
color_dark_ground = libtcod.Color(50, 50, 150)

color_light_wall = libtcod.Color(130, 110, 50)
color_light_ground = libtcod.Color(200, 180, 50)

# TODO: make choice
global old_map_style
old_map_style = False

global show_corpses
show_corpses = False

main_menu()


