import pcbnew
import json
import re
import copy
from dataclasses import dataclass

@dataclass
class LayoutData:
    offsetX:float
    offsetY:float
    refs:list[str]

# keyboard-layout.json のパス
KLE_PATH = 'C:/work/self_made_keyboard/ega-right-kb/ega-right-kb/keyboard-layout.json'
with open(KLE_PATH) as f:
    data = json.load(f)

#######################
# Parse json data
#######################
layouts = []
rows = []
for each_data in data:
    _offsetX = 0
    _offsetY = 0
    _refs = []
    for field in each_data:
        if type(field) is dict:
            # 1行に複数の配置指示があり得るので、新しい指示を検出したタイミングでLayoutDataを追加
            if len(_refs) != 0:
                layout = LayoutData(offsetX=_offsetX, offsetY=_offsetY, refs=copy.deepcopy(_refs))
                layouts.append(layout)
                _refs.clear()
            # offsetの取得
            keys = field.keys()
            if 'x' in keys:
                _offsetX = field.get('x')
            if 'y' in keys:
                _offsetY = field.get('y')
            # widthやrotationなどに対応するならここで追加していけばよい
        else:
            # key Refの取得(SW0~SW999まで対応)
            ref = re.search(r'SW[0-9]{1,3}', field)
            if ref is not None:
                _refs.append(ref.group())
  
    # LayoutDataを追加
    if len(_refs) != 0:
        layout = LayoutData(offsetX=_offsetX, offsetY=_offsetY, refs=copy.deepcopy(_refs))
        layouts.append(layout)
        _refs.clear()
    # 1行分のデータをadd
    if len(layouts) != 0:
        rows.append(copy.deepcopy(layouts))
        layouts.clear()


#######################
# Change layout of kicad
#######################
SW_WIDTH = 19.05   # or CherryMX
SW_HEIGHT = 19.05
ORIGIN_X = 50  # シートの左上が(X,Y) = (0,0)
ORIGIN_Y = 50  # シートサイズ、スイッチのレイアウトに合わせて適宜調整

prev_x = 0
prev_y = 0
x = 0
y = 0
board = pcbnew.GetBoard()
for row_i, row in enumerate(rows):
    # 新しい行に移るたびにcol方向位置はリセット
    prev_x = 0
    for layout_i, layout in enumerate(row):
        x = prev_x + SW_WIDTH + (layout.offsetX * SW_WIDTH)
        # 行内におけるyの値は全て共通なので1回だけ更新する
        if layout_i == 0:
            y = prev_y + SW_HEIGHT + (layout.offsetY * SW_HEIGHT)
        # キーの配置
        for i, keyref in enumerate(layout.refs):
            sw = board.FindFootprintByReference(keyref)
            sw.SetPosition(pcbnew.VECTOR2I_MM(x + (i * SW_WIDTH) + ORIGIN_X , y + ORIGIN_Y)) 
            # 起点になるcol方向位置は1つキーを置くごとに1つずれていく
            prev_x = x + (i * SW_WIDTH)
    
    # 1行分終わったらrow方向の起点位置を更新
    prev_y = y
        

pcbnew.Refresh()

# EOF
