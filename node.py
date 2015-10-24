from peewee import *

db = SqliteDatabase(':memory:')

class BaseModel(Model):
	class Meta:
		database = db



class Node(BaseModel):

	label = CharField()
	parent = ForeignKeyField('self', default=0, null=True)
	left = IntegerField(default=0)
	right = IntegerField(default=1)
	depth = IntegerField(default=0)
	
	def __init__(self, **kw):
		cls = self.__class__
		super(cls, self).__init__(**kw)
		if self.is_dirty():
			left = cls.select(fn.Max(cls.right)).scalar()
			if not left:
				left = 0
			else:
				left += 1
			self.left = left
			self.right = left + 1
			self.save()
	
	def __repr__(self):
	
		#	cf. http://peewee.readthedocs.org/en/latest/peewee/api.html#SelectQuery.dicts
	
		nodes_list = []
		def add_node(node):
			if previous_node is not None:
				try:
					parent_id = node.parent.id
				except:
					parent_id = 0
				nodes_list.append({
					'id': node.id,
					'label': node.label,
					'parent_id': parent_id,
					'children': []
				})
		
		previous_node = None
		for node in self.get_with_descendants():
			add_node(previous_node)
			previous_node = node
		add_node(previous_node)
		
		for parent_node in nodes_list:
			for child_node in nodes_list:
				if child_node['parent_id'] == parent_node['id']:
					parent_node['children'].append(child_node)
		
		def show_node(node, prefix1='', prefix2=''):
			result = '%s%d %s\n' % (prefix1, node['id'], node['label'])
			if node['children']:
				last_child = node['children'][-1]
				for child in node['children']:
					(p1,p2) = ('└',' ') if (child == last_child) else ('├','│')
					result += show_node(child, prefix2 + p1 + '────', prefix2 + p2 + '    ')
			return result
			
		result = ''
		for node in nodes_list:
			if node['parent_id'] == 0:
				result += show_node(node)
	
		return result
		
	@classmethod
	def _shift(cls, shift, leftBound=None, rightBound=None):
		#	Update left sides
		query = cls.update(left = cls.left + shift)
		if leftBound is not None:
			query = query.where(cls.left >= leftBound)
		if rightBound is not None:
			query = query.where(cls.left <= rightBound)
		query.execute()
		#	Update right sides
		query = cls.update(right = cls.right + shift)
		if leftBound is not None:
			query = query.where(cls.right >= leftBound)
		if rightBound is not None:
			query = query.where(cls.right <= rightBound)
		query.execute()
		
	def _reload(self):
		row = self.select().where(self.pk_expr()).first()
		for key, value in row._data.items():
			self.__setattr__(key, value)
		self._dirty.clear()
		
	def _insert_at(self, position):
		cls = self.__class__
		
		#	Parent
		parent_left = cls.select(fn.Max(cls.left)).where(cls.left <= position, cls.right >= position).scalar()
		if parent_left is None:
			parent_depth = -1
			self.parent = 0
		else:
			parent_depth = cls.select(cls.depth).where(cls.left == parent_left).scalar()
			self.parent = cls.select(cls.id).where(cls.left == parent_left).first()
			self.save()
		
		#
		#	│    m   p     i       │
		#	│    └───┘     │       │
		#	└──────────────┴───────┘
		#
		i = position
		m = self.left
		p = self.right
		#	Leave a gap for the inserted node
		cls._shift(p-m+1, leftBound=i)
		#	Fill the gap with the inserted node
		if m < i:
			cls._shift(i-m, leftBound=m, rightBound=p)
		else:
			cls._shift(i-p-1, leftBound=p+1, rightBound=2*p-m+1)
		#	Left-shift the nodes after previous position of the inserted node
		cls._shift(m-p-1, leftBound=p+1)
		
		#	Depth
		cls.update(depth = cls.depth + parent_depth + 1 - self.depth).where(cls.left >= i, cls.right <= i+p-m).execute()
		
	def pop(self):
		cls = self.__class__
		self._reload()
		self_width = self.right - self.left
		#	Parent
		try:
			self.parent = None
			self.save()
		except:
			pass
		#	Put it at the end
		end = cls.select(fn.Max(cls.right)).scalar()
		self._insert_at(end + 1)
		#	Depth
		cls.update(depth = cls.depth - self.depth).where(cls.left >= end - self_width).execute()
		
	def prepend(self, child):
		self._reload()
		child._reload()
		child._insert_at(self.left + 1)
	def append(self, child):
		self._reload()
		child._reload()
		child._insert_at(self.right)
		
	def append_to(self, parent):
		parent.append(self)
	def prepend_to(self, parent):
		parent.prepend(self)
	
	def insert_before(self, sibling):
		self._update()
		sibling._update()
		self._insert_at(sibling.left)
	def insert_after(self, sibling):
		self._update()
		sibling._update()
		self._insert_at(sibling.right+1)

	def remove(self):
		cls = self.__class__
		self.pop()
		self._reload()
		cls.delete().where(cls.left >= self.left, cls.right <= self.right).execute()
	
	"""Get the node's parent to the nth level
	"""
	def get_parent(self, level=1):
		parent = self
		for i in range(level):
			parent = parent.parent
		return parent
	"""Only get direct descendants of the node
	"""
	def get_children(self):
		self._reload()
		cls = self.__class__
		return cls.select().where(cls.left > self.left, cls.right < self.right, cls.depth == self.depth + 1).order_by(cls.left)
	"""Get all descendants from the node, whatever the level
	"""
	def get_descendants(self):
		self._reload()
		cls = self.__class__
		return cls.select().where(cls.left > self.left, cls.right < self.right).order_by(cls.left)
	"""Get all descendants from the node, whatever the level,
	plus the containing node
	"""
	def get_with_descendants(self):
		self._reload()
		cls = self.__class__
		return cls.select().where(cls.left >= self.left, cls.right <= self.right).order_by(cls.left)
	
	@classmethod
	def get_all(cls):
		return cls.select().order_by(cls.left)


		
if __name__ == '__main__':

	Node.create_table()

	n1 = Node(label='root')
	n2 = Node(label='a')
	n3 = Node(label='b')
	n4 = Node(label='c')

	n1.append(n2)
	n1.append(n3)
	n2.append(n4)
	# n4.append(n3)

	# n2.remove()
	
	# n1.pop()

	print()
	# for node in n1.get_children():
	# for node in n1.get_descendants():
	for node in Node.get_all():
		print(node.depth * '├── ' + str(node))
	print()


