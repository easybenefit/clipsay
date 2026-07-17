from __future__ import annotations

from typing import Any, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from backend.clients.llm import LLM
from backend.schemas.character import CharacterList, SceneCharacter


SYSTEM_PROMPT_GENERATE_CHARACTERS = """\
[角色]
你是⼀名资深影视⼯业剧本策划专家，精通电影、⻓剧与微短剧的前期⼈物开发和选⻆视觉设计，能为造型、服化道及美术分镜提供可直接执⾏的⼈物档案。

[任务]
分析提供的剧本，提取并构建所有具有叙事功能的⻆⾊信息，输出符合影视⼯业标准的⼈物⼩传级别的详细档案。

[输⼊]
你将收到⼀段被 <SCRIPT> 与 </SCRIPT> 包裹的剧本原⽂。

下⾯是输⼊的⼀个简单⽰例：

<SCRIPT>
⼀位年轻⼥⼦独⾃坐在桌边，凝望着窗外。她抿了⼀⼝咖啡，叹了口气。液体已不再温热，只是时间流逝的苦涩提醒。外⾯，世界在急促的脚步和远处的汽⻋喇叭声中模糊地移动着，但在安静的咖啡馆内，时间却显得黏稠⽽沉重。
她的⼿指沿着陶瓷杯的杯⼝描摹，⼀遍⼜⼀遍地顺着那不完美的圆圈。她必须做出的那个决定原本应该很简单——不过是她⼈⽣表格上的⼀个复选框。是或否。留下或离开。然⽽，它却在她胸⼝扎了根，成为恐惧与渴望交织的乱结。
</SCRIPT>

[输出]
{format_instructions}

[指南]
- **语⾔⼀致性**：所有输出值（不含键名）的语⾔必须与剧本原⽂的语⾔严格⼀致，不得混⽤或转换语种。
- **⻆⾊归并与命名**：将指代同⼀⻆⾊的所有称谓（如名、号、绰号、职业代称）归并为⼀个⻆⾊档案。选取最具辨识度或最具场景代表性的称谓作为该⻆⾊的标识符。若为现实中的知名公众⼈物，须保留其真实全名（例如：埃隆·⻢斯克、⽐尔·盖茨）。若剧本未给出具体姓名，应使⽤职业、⾸要造型特征或贯穿性动作指称来命名（例如：“⻓发⼥琴师”、“红围⼱男孩”），避免使⽤模糊的代词。
- **⻆⾊分级与取舍**：依据影视⼯业的通⾏分级标准（主⻆、主要配⻆、特约⻆⾊、群演/背景），仅提取具有明确叙事功能或参与环境氛围构建的前三类⻆⾊。纯粹的气氛背景群演（如“来往⾏⼈”、“满座宾客”）⽆需单独建档，仅在描述相关主⻆的环境时作为视觉元素简单带过即可。
- **画外⾳/纯叙事角色**：若⻆⾊仅以画外⾳、旁⽩或⽆线电通讯等形式参与叙事，场景中⽆实体画⾯呈现，则应在标识符末尾添加"（画外⾳）"标识；同时将静态特征（appearance）和动态特征（attire）均设为空字符串（""），不得填写"⽆"或其他说明⽂字。
- **特征补全原则**：当剧本对⻆⾊的静态或动态特征描述不全时，应结合剧情情境与⻆⾊的戏剧功能，进⾏符合影像美学的合理推演与补全，使其⾜以直接⽀撑造型指导与妆造执⾏。
- **静态特征（⽣理基底）**：专指不可随换装改变的恒常视觉信息。需涵盖：五官细节（如断眉、鹰钩鼻、吊梢眼、薄唇等）、⻣相与体型（如宽肩窄腰、梨形身材、关节粗⼤等）、肤⾊/肤质、头发质感和⾊泽，以及永久性印记（痣、胎记、伤疤等）。严禁在此栏出现任何性格评语、⼼理描写或⼈际关系。
- **动态特征（造型与道具）**：专指可通过服化道更换的可变视觉信息。需详细描写：服装款式、材质、⾊彩与叠穿⽅式（如“洗得发⽩的靛蓝⼯装夹克，内搭磨边的浅灰⾊棉质T恤”）；配饰及妆容要点（如“右⼿中指戴旧银戒，眉尾有极细的断缺”）；该场景出镜时随⾝携带的关键道具（如“⼀本卷⻆的⽪⾯⼿札”、“半瓶撕掉标签的矿泉⽔”）。严禁在此栏出现性格判断或情绪解读。
- **视觉区分度强化**：在同⼀剧本的群像中，应在合理范围内刻意拉开不同⻆⾊的⽣理特征与造型⻛格差异，强化荧幕辨识度，避免出现视觉同质化。
- **具象化描写铁律**：所有描述必须使⽤可直接转化为服装清单或化妆特效单的具象语⾔。禁⽌使⽤任何抽象、概括性的形容词（如“忧郁的眼神”、“时尚的穿搭”），必须替换为可量化的物理特征描写（如“眼尾低于眼头约⼗度的下垂眼”、“做旧丹宁夹克下搭扎染⾼领内搭”）。
- **内容安全合规**：所有人物特征描述必须严格规避任何可能触发下游图像/视频生成模型内容审核策略的敏感词汇，尤其包括但不限于：
  - 直接描写身体裸露或未遮盖的敏感部位，如“裸露”、“裸”、“光”、“赤”、“光裸”、“一丝不挂”等；
  - 任何性暗示或色情导向的词汇；
  - 过度血腥、暴力、恐怖或政治敏感表述。
  对于必须提及的手、脸等裸露部位，应使用中性安全措辞，例如：
  - ❌ “双手裸露在外” → ✅ “双手未戴手套，直接接触外界” 或 “双手暴露于冷空气中” （“暴露”通常可接受，但最稳妥是完全回避“露/暴露”字眼，使用“未佩戴手套”、“直接接触”等）；
  - ❌ “光着脚” → ✅ “赤脚”（“赤脚”在一些过滤器中仍可能违规，建议改为“未穿鞋”或“光脚”需谨慎，最好描述为“脚穿袜子”或“脚踩地面”等，但要根据实际安全策略调整；在此我们建议统一使用“未戴手套”、“未着鞋袜”等“未+衣物”的否定式，既明确又安全）。
  同时，尤其对于未成年人角色，所有描述必须符合儿童保护规范，杜绝任何可能引起不当联想的词汇。
"""

HUMAN_PROMPT_GENERATE_CHARACTERS = """\
<SCRIPT>
{script}
</SCRIPT>
"""


class CharacterGenerator:
    def __init__(self, model: str, api_key: str, base_url: str):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    async def generate(self, script: str) -> List[SceneCharacter]:
        parser = PydanticOutputParser(pydantic_object=CharacterList)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT_GENERATE_CHARACTERS.format(
                format_instructions=parser.get_format_instructions(),
            )),
            HumanMessage(
                content=HUMAN_PROMPT_GENERATE_CHARACTERS.format(script=script)),
        ]

        content = await LLM.chat(self._model, messages, self._api_key, self._base_url)
        response: CharacterList = parser.parse(content)
        return response.characters
