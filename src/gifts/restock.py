from dataclasses import dataclass


@dataclass(frozen=True)
class GiftSource:
    name: str
    shop: str
    price: int
    characters: tuple[str, ...]

    def label(self) -> str:
        return f"{self.name}（{self.shop}，表内标价 {self.price:,}）"


# 「角色属性」的「礼物信息」页。仅收录有来源的常规 +400 礼物。
_FAVORITE_GIFTS = (
    GiftSource("泠泠琉光", "集山忘野", 5400, ("法帝娅",)),
    GiftSource("静夜方灯", "Mr.Brown", 18000, ("海月",)),
    GiftSource("复古暖灯", "Mr.Brown", 15000, ("曳尔沐",)),
    GiftSource("清影台灯", "Mr.Brown", 10000, ("Exe",)),
    GiftSource("白玉盏", "Mr.Brown", 20000, ("翳",)),
    GiftSource("几何夜", "Oops！Chest", 10000, ("埃德嘉", "伊洛伊")),
    GiftSource("约定", "Oops！Chest", 10000, ("阿德勒", "达芙蒂尔", "海月")),
    GiftSource("幽梦", "Oops！Chest", 10000, ("伊洛伊", "曳尔沐")),
    GiftSource("跳跳兔盒", "Mr.Brown", 20000, ("早雾", "安魂曲", "小吱")),
    GiftSource("金月", "Mr.Brown", 15000, ("浔", "真红", "伊洛伊", "灵可")),
    GiftSource("轨道之心", "Mr.Brown", 20000, ("哈索尔", "九原", "卡厄斯")),
    GiftSource("暴走棉绒绒-肌肉信仰", "DSD", 12000, ("白藏",)),
    GiftSource("暴走棉绒绒-强者之证", "DSD", 12000, ("白藏", "真红")),
    GiftSource("暴走棉绒绒-黑暗降临", "扭蛋商店", 20, ("白藏",)),
    GiftSource("心猎铁骑L1-静待胜机", "DSD", 14400, ("娜娜莉", "卡厄斯")),
    GiftSource("心猎铁骑L1-邪恶粉碎", "DSD", 14400, ("娜娜莉", "卡厄斯")),
    GiftSource("心猎铁骑L3-英雄登场", "DSD", 14400, ("真红",)),
    GiftSource("浅绯祈-月影流光", "DSD", 18000, ("薄荷", "哈尼娅")),
    GiftSource("浅绯祈-绯红之名", "DSD", 18000, ("薄荷", "哈尼娅")),
    GiftSource("心猎铁骑L1-必杀一击", "扭蛋商店", 20, ("娜娜莉",)),
    GiftSource("浅绯祈-暮色银辉", "扭蛋商店", 20, ("薄荷", "哈尼娅")),
    GiftSource("此声未刻录", "Exile on Main St.", 15000, ("埃德嘉", "明音凛")),
    GiftSource("显像屏", "Mr.Brown", 25000, ("Exe",)),
    GiftSource("拉普本", "Mr.Brown", 25000, ("Exe",)),
    GiftSource("溶月茶具", "Oops！Chest", 15000, ("残虹", "黑羽")),
    GiftSource("映像机", "Mr.Brown", 22000, ("曳尔沐",)),
    GiftSource("琉璃影屏", "超规格", 18000, ("黑羽",)),
    GiftSource("「九百九十九夜」", "DSD", 15000, ("真红", "伊洛伊", "曳尔沐")),
    GiftSource("曲曲小仔", "噗卡淘淘铺", 12000, ("薄荷", "埃德嘉", "真红")),
    GiftSource("棒棒小仔", "噗卡淘淘铺", 12000, ("真红",)),
    GiftSource("酥酥小仔", "噗卡淘淘铺", 12000, ("哈尼娅", "真红")),
    GiftSource("松松小仔", "噗卡淘淘铺", 12000, ("真红",)),
)
_COTTON = GiftSource("绒绒棉花", "迷迭兑换", 15, ())


def restock_message(characters: list[str]) -> str:
    lines = ["首屏未确认有库存的 +400 礼物", "涉及角色 " + "、".join(characters)]
    for character in characters:
        gifts = [gift.label() for gift in _FAVORITE_GIFTS if character.strip() in gift.characters]
        if gifts:
            lines.append(f"{character}可补 " + "、".join(gifts[:2]))
    lines.append(f"通用 +400 可领周常绒绒棉花，也可兑换{_COTTON.label()}")
    return "\n".join(lines)
