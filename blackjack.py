import random
from functools import partial

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

from common import (
    BETS,
    BLUE,
    FONT_SUITS,
    FONT_TITLE,
    GOLD,
    GRAY,
    GREEN,
    RED,
    SOFT_RED,
    WHITE,
    GLabel,
    MessageLabel,
    Page,
    RoundButton,
    TopBar,
    float_text,
    go_to,
    pulse,
)

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["S", "H", "D", "C"]  # spades, hearts, diamonds, clubs
SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
CARD_DELAY = 0.3  # pause between dealt cards
RED_CARD = (0.85, 0.1, 0.1, 1)
BLACK_CARD = (0.1, 0.1, 0.12, 1)


def new_deck():
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append((rank, suit))
    random.shuffle(deck)
    return deck


def hand_value(hand):
    total = 0
    aces = 0
    for card in hand:
        rank = card[0]
        if rank == "A":
            aces = aces + 1
            total = total + 11
        elif rank == "J" or rank == "Q" or rank == "K":
            total = total + 10
        else:
            total = total + int(rank)
    while total > 21 and aces > 0:
        total = total - 10
        aces = aces - 1
    return total


class CardView(BoxLayout):
    """A playing card. Starts face down or face up, can flip over."""

    def __init__(self, card, hidden, **kwargs):
        super().__init__(orientation="vertical", padding=(0, 6), **kwargs)
        self.card = card
        self.hidden = hidden
        self.full_width = 58
        self.size_hint = (None, None)
        self.size = (self.full_width, 86)
        self.pos_hint = {"center_y": 0.5}

        with self.canvas.before:
            Color(0, 0, 0, 0.3)
            self.shadow = RoundedRectangle(radius=[10])
            self.face_color = Color(1, 1, 1, 1)
            self.bg = RoundedRectangle(radius=[10])

        self.rank_label = Label(font_name=FONT_TITLE, font_size=24)
        self.suit_label = Label(font_name=FONT_SUITS, font_size=32)
        self.add_widget(self.rank_label)
        self.add_widget(self.suit_label)

        self.bind(pos=self.update_bg, size=self.update_bg)
        self.show_side()

    def update_bg(self, *args):
        self.shadow.pos = (self.x + 2, self.y - 3)
        self.shadow.size = self.size
        self.bg.pos = self.pos
        self.bg.size = self.size

    def show_side(self):
        if self.hidden:
            self.face_color.rgba = (0.15, 0.3, 0.7, 1)
            self.rank_label.text = ""
            self.suit_label.text = "♦"
            self.suit_label.color = (0.55, 0.7, 1, 1)
        else:
            self.face_color.rgba = (1, 1, 1, 1)
            suit = self.card[1]
            if suit == "H" or suit == "D":
                color = RED_CARD
            else:
                color = BLACK_CARD
            self.rank_label.text = self.card[0]
            self.rank_label.color = color
            self.suit_label.text = SUIT_SYMBOLS[suit]
            self.suit_label.color = color

    def flip_up(self):
        """Turns a face-down card face up: narrows, swaps the side, widens."""
        self.rank_label.opacity = 0
        self.suit_label.opacity = 0
        anim = Animation(width=2, duration=0.15)
        anim.bind(on_complete=self.finish_flip)
        anim.start(self)

    def finish_flip(self, *args):
        self.hidden = False
        self.show_side()
        self.rank_label.opacity = 1
        self.suit_label.opacity = 1
        Animation(width=self.full_width, duration=0.15).start(self)


def make_row():
    row = BoxLayout(size_hint_y=0.2, spacing=6)
    row.left_spacer = Widget()
    row.right_spacer = Widget()
    row.add_widget(row.left_spacer)
    row.add_widget(row.right_spacer)
    return row


class BlackjackScreen(Screen):
    def __init__(self, wallet, **kwargs):
        super().__init__(**kwargs)
        self.wallet = wallet
        self.bet_index = 0
        self.bet = 0
        self.deck = []
        self.player = []
        self.dealer = []
        self.player_views = []
        self.dealer_views = []
        self.dealer_hidden = True
        self.in_round = False
        self.busy = False

        root = Page(padding=16, spacing=8)

        self.top_bar = TopBar(self.go_menu)
        root.add_widget(self.top_bar)

        title = GLabel(
            text="BLACKJACK", font_size=32, color=GOLD, size_hint_y=0.08
        )
        root.add_widget(title)

        self.dealer_label = GLabel(font_size=20, size_hint_y=0.06)
        root.add_widget(self.dealer_label)
        self.dealer_row = make_row()
        root.add_widget(self.dealer_row)

        self.message_label = MessageLabel(size_hint_y=0.1)
        root.add_widget(self.message_label)

        self.player_row = make_row()
        root.add_widget(self.player_row)
        self.player_label = GLabel(font_size=20, size_hint_y=0.06)
        root.add_widget(self.player_label)

        self.controls = BoxLayout(spacing=10, size_hint_y=0.13)
        root.add_widget(self.controls)

        self.bet_button = RoundButton(btn_color=GRAY)
        self.bet_button.bind(on_release=self.change_bet)
        self.deal_button = RoundButton(text="РАЗДАТЬ", btn_color=GREEN)
        self.deal_button.bind(on_release=self.deal)
        self.hit_button = RoundButton(text="ЕЩЁ", btn_color=BLUE)
        self.hit_button.bind(on_release=self.hit)
        self.stand_button = RoundButton(text="ХВАТИТ", btn_color=RED)
        self.stand_button.bind(on_release=self.stand)

        self.add_widget(root)

    def on_pre_enter(self, *args):
        self.in_round = False
        self.set_busy(False)
        self.player = []
        self.dealer = []
        self.clear_table()
        self.message_label.color = WHITE
        self.message_label.text = "Сделай ставку"
        self.refresh_totals()
        self.show_idle_controls()

    def go_menu(self, *args):
        if self.in_round or self.busy:
            self.message_label.color = SOFT_RED
            self.message_label.text = "Сначала доиграй раунд"
            return
        go_to(self.manager, "menu", "right")

    # ----- ui -----

    def current_bet(self):
        return BETS[self.bet_index]

    def set_busy(self, flag):
        self.busy = flag
        self.deal_button.disabled = flag
        self.hit_button.disabled = flag
        self.stand_button.disabled = flag

    def show_idle_controls(self):
        self.controls.clear_widgets()
        self.controls.add_widget(self.bet_button)
        self.controls.add_widget(self.deal_button)
        self.bet_button.text = "Ставка: " + str(self.current_bet())
        self.top_bar.set_balance(self.wallet.balance)

    def show_play_controls(self):
        self.controls.clear_widgets()
        self.controls.add_widget(self.hit_button)
        self.controls.add_widget(self.stand_button)
        self.top_bar.set_balance(self.wallet.balance)

    def change_bet(self, *args):
        if self.busy or self.in_round:
            return
        self.bet_index = self.bet_index + 1
        if self.bet_index >= len(BETS):
            self.bet_index = 0
        self.bet_button.text = "Ставка: " + str(self.current_bet())

    def clear_row(self, row):
        row.clear_widgets()
        row.add_widget(row.left_spacer)
        row.add_widget(row.right_spacer)

    def clear_table(self):
        self.clear_row(self.dealer_row)
        self.clear_row(self.player_row)
        self.player_views = []
        self.dealer_views = []

    def add_card_view(self, row, views, card, hidden):
        view = CardView(card, hidden)
        view.width = 8
        view.opacity = 0
        row.remove_widget(row.right_spacer)
        row.add_widget(view)
        row.add_widget(row.right_spacer)
        views.append(view)
        Animation(
            width=view.full_width, opacity=1, duration=0.25, t="out_quad"
        ).start(view)

    def refresh_totals(self):
        """Totals count only the cards already shown on the table."""
        shown_player = self.player[: len(self.player_views)]
        shown_dealer = self.dealer[: len(self.dealer_views)]

        if len(shown_player) == 0:
            self.player_label.text = "Игрок"
        else:
            self.player_label.text = "Игрок: " + str(hand_value(shown_player))

        if len(shown_dealer) == 0 or self.dealer_hidden:
            self.dealer_label.text = "Дилер"
        else:
            self.dealer_label.text = "Дилер: " + str(hand_value(shown_dealer))

    # ----- dealing animation -----

    def sync_cards(self, done):
        """Puts missing cards on the table one by one, then calls done()."""
        player_count = len(self.player_views)
        dealer_count = len(self.dealer_views)

        if player_count < len(self.player) and player_count <= dealer_count:
            card = self.player[player_count]
            self.add_card_view(self.player_row, self.player_views, card, False)
        elif dealer_count < len(self.dealer):
            card = self.dealer[dealer_count]
            hidden = self.dealer_hidden and dealer_count == 1
            self.add_card_view(self.dealer_row, self.dealer_views, card, hidden)
        elif player_count < len(self.player):
            card = self.player[player_count]
            self.add_card_view(self.player_row, self.player_views, card, False)
        else:
            self.refresh_totals()
            done()
            return

        self.refresh_totals()
        Clock.schedule_once(partial(self.sync_next, done), CARD_DELAY)

    def sync_next(self, done, dt):
        self.sync_cards(done)

    def call_done(self, done, dt):
        done()

    def reveal_dealer(self, done):
        """Flips the dealer's hidden card, then calls done()."""
        self.dealer_hidden = False
        if len(self.dealer_views) > 1:
            self.dealer_views[1].flip_up()
        Clock.schedule_once(self.refresh_totals_later, 0.35)
        Clock.schedule_once(partial(self.call_done, done), 0.6)

    def refresh_totals_later(self, dt):
        self.refresh_totals()

    # ----- game logic -----

    def deal(self, *args):
        if self.busy or self.in_round:
            return
        bet = self.current_bet()
        if not self.wallet.can_pay(bet):
            self.message_label.color = SOFT_RED
            self.message_label.text = "Не хватает фишек, уменьши ставку"
            return

        self.bet = bet
        self.wallet.take(bet)
        self.top_bar.set_balance(self.wallet.balance)
        self.deck = new_deck()
        self.player = []
        self.dealer = []
        self.player.append(self.deck.pop())
        self.dealer.append(self.deck.pop())
        self.player.append(self.deck.pop())
        self.dealer.append(self.deck.pop())
        self.dealer_hidden = True
        self.in_round = True
        self.set_busy(True)
        self.clear_table()
        self.message_label.color = WHITE
        self.message_label.text = "Раздаём..."
        self.sync_cards(self.after_deal)

    def after_deal(self):
        if hand_value(self.player) == 21:
            self.reveal_dealer(self.natural_result)
            return
        self.message_label.text = "Твой ход"
        self.show_play_controls()
        self.set_busy(False)

    def natural_result(self):
        if hand_value(self.dealer) == 21:
            self.finish_round("push", "Оба блэкджек, ничья")
        else:
            self.finish_round("blackjack", "Блэкджек!")

    def hit(self, *args):
        if self.busy or not self.in_round:
            return
        self.set_busy(True)
        self.player.append(self.deck.pop())
        self.sync_cards(self.after_hit)

    def after_hit(self):
        value = hand_value(self.player)
        if value > 21:
            self.reveal_dealer(self.bust_result)
        elif value == 21:
            self.start_dealer()
        else:
            self.set_busy(False)

    def bust_result(self):
        self.finish_round("lose", "Перебор")

    def stand(self, *args):
        if self.busy or not self.in_round:
            return
        self.set_busy(True)
        self.start_dealer()

    def start_dealer(self):
        self.message_label.text = "Ходит дилер..."
        self.reveal_dealer(self.dealer_turn)

    def dealer_turn(self):
        """Dealer takes cards one at a time until 17 or more."""
        if hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
            self.sync_cards(self.dealer_turn)
            return
        self.evaluate()

    def evaluate(self):
        player_value = hand_value(self.player)
        dealer_value = hand_value(self.dealer)
        if dealer_value > 21:
            self.finish_round("win", "У дилера перебор")
        elif player_value > dealer_value:
            self.finish_round("win", "Ты победил")
        elif player_value == dealer_value:
            self.finish_round("push", "Ничья")
        else:
            self.finish_round("lose", "Дилер выиграл")

    def finish_round(self, outcome, text):
        bet = self.bet
        payout = 0
        if outcome == "blackjack":
            payout = bet * 2 + bet // 2
        elif outcome == "win":
            payout = bet * 2
        elif outcome == "push":
            payout = bet

        if payout > 0:
            self.wallet.add(payout)

        net = payout - bet
        if net > 0:
            text = text + ": +" + str(net)
            self.message_label.color = GOLD
            pulse(self.message_label)
            float_text(self, "+" + str(net), GOLD, 0.45)
        elif net < 0:
            text = text + ": -" + str(bet)
            self.message_label.color = SOFT_RED
        else:
            self.message_label.color = WHITE

        if self.wallet.refill_if_broke():
            self.message_label.color = WHITE
            text = "Фишки кончились, держи новые"

        self.in_round = False
        self.message_label.text = text
        self.refresh_totals()
        self.show_idle_controls()
        self.set_busy(False)
