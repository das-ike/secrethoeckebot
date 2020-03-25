#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = "Julian Schrittwieser & Jannis Langmaack"

import logging as log
import random
import re
from random import randrange
from time import sleep
import json

from os import system
from Board import Board
from Constants import players
from Game import Game
from Player import Player

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler,
                          ConversationHandler, CallbackQueryHandler)
from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)

from Config import TOKEN
from Config import ADMIN

# Enable logging
log.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                level=log.INFO,
                filename='../logs/logging.log')

logger = log.getLogger(__name__)

games = {}

commands = [  # command description used in the "hilfe" command
    '/help - Gibt dir Informationen zu den verfügbaren Befehlen.',
    '/start - Gibt dir grundlegende Informationen zu Secret Höcke.',
    '/symbols - Zeigt dir alle möglichen Symbole auf dem Spielbrett.',
    '/rules - Gibt dir einen Link zu den offiziellen Secret Höcke Regeln.',
    '/newgame - Erstellt ein neues Spiel.',
    '/join - Tritt einem existierenden Spiel bei.',
    '/startgame - Startet ein existierendes Spiel, wenn alle Spieler beigetreten sind.',
    '/cancelgame - Beendet ein existierendes Spiel. Alle Spielstände werden gelöscht.',
    '/board - Zeigt das aktuelle Spielbrett mit den Gesetzen der extremen Mitte und der Faschisten, der Reihenfolge der Präsidenten und dem Wahlzähler.'
]

symbols = [
    u"\u25FB\uFE0F" + ' Leeres Feld ohne spezielle Macht',
    u"\u2716\uFE0F" + ' Feld mit Karte belegt',  # X
    u"\U0001F52E" + ' Präsidialmacht: Vorschau auf Gesetze',  # crystal
    u"\U0001F50E" + ' Präsidialmacht: Gesinnung untersuchen',  # inspection glass
    u"\U0001F5E1" + ' Präsidialmacht: Hinrichtung',  # knife
    u"\U0001F454" + ' Präsidialmacht: Spezielle Präsidentschaftswahl',  # tie
    u"\U0001F54A" + ' PARTEI-Genossinnen gewinnen',  # dove
    u"\u2620" + ' Faschisten gewinnen'  # skull
]


def command_symbols(bot, update):
    cid = update.message.chat_id
    symbol_text = "Die folgenden Symbole können auf dem Spielbrett erscheinen: \n"
    for i in symbols:
        symbol_text += i + "\n"
    bot.send_message(cid, symbol_text)


def command_board(bot, update):
    cid = update.message.chat_id
    if cid in games.keys():
        if games[cid].board is not None:
            bot.send_message(cid, games[cid].board.print_board())
        else:
            bot.send_message(cid, "In diesem Chat befindet sich kein laufendes Spiel. Bitte starte ein Spiel mit /startgame")
    else:
        bot.send_message(cid, "In diesem Chat existiert kein Spiel. Erstelle ein neues Spiel mit /newgame")


def command_start(bot, update):
    cid = update.message.chat_id
    bot.send_message(cid,
                     "\"Secret Höcke ist ein Brett-, Karten- und Deduktionsspiel für 5-10 Menschen."
					 " Ziel des Spiels ist es, den Secret Höcke zu finden und aufzuhalten."
                     " Die Mehrheit der Spieler sind PARTEI-Genossinnen. Wenn sie lernen, sich gegenseitig zu vertrauen, haben sie "
                     "genügend Stimmen, um den Tisch zu kontrollieren und das Spiel zu gewinnen. Doch manche Spieler sind Faschisten."
                     " Sie werden alles sagen, was nötig ist, um gewählt zu werden, ihre Agenda durchsetzen und die anderen Spieler beschuldigen. The liberals must "
                     " Die PARTEI-Genossinnen müssen zusammenarbeiten, um die Wahrheit herauszufinden, bevor die Faschisten ihren kaltblütigen Führer "
                     "an die Spitze der Regierung setzen und das Spiel gewinnen.\"\n- Offizielle Beschreibung von Secret Höcke\n\nFüge mich zu einer Gruppe hinzu und schreibe /newgame, um zu spielen!")
    command_help(bot, update)


def command_rules(bot, update):
    cid = update.message.chat_id
    btn = [[InlineKeyboardButton("Regeln", url="http://www.secrethitlerfree.de/")]]
    rulesMarkup = InlineKeyboardMarkup(btn)
    bot.send_message(cid, "Lies die offiziellen Secret Höcke Regeln:", reply_markup=rulesMarkup)


# pings the bot
def command_ping(bot, update):
    cid = update.message.chat_id
    bot.send_message(cid, 'pong - v0.2')


# prints statistics, only ADMIN
def command_stats(bot, update):
    cid = update.message.chat_id
    if cid == ADMIN:
        with open("stats.json", 'r') as f:
            stats = json.load(f)
        stattext = "+++ Statistiken +++\n" + \
                    "PARTEI-Genossin Siege (Gesetze): " + str(stats.get("libwin_policies")) + "\n" + \
                    "PARTEI-Genossin Siege (Höcke getötet): " + str(stats.get("libwin_kill")) + "\n" + \
                    "Faschist Siege (Gesetze): " + str(stats.get("fascwin_policies")) + "\n" + \
                    "Faschist Siege (Höcke Kanzler): " + str(stats.get("fascwin_hitler")) + "\n" + \
                    "Spiele abgebrochen: " + str(stats.get("cancelled")) + "\n\n" + \
                    "Gesamtanzahl an Gruppen: " + str(len(stats.get("groups"))) + "\n" + \
                    "Aktuell laufende Spiele: " + str(len(games))
        bot.send_message(cid, stattext)


# help page
def command_help(bot, update):
    cid = update.message.chat_id
    help_text = "Die folgenden Befehle sind verfügbar:\n"
    for i in commands:
        help_text += i + "\n"
    bot.send_message(cid, help_text)


# reboot, only ADMIN
def command_reboot(bot, update):
    cid = update.message.chat_id
    if cid == ADMIN:
        bot.send_message(cid, 'Jetzt neustarten!')
        system('sudo reboot')

# broadcast message to all groups, only ADMIN
def command_broadcast(bot, update, args):
    cid = update.message.chat_id
    if cid == ADMIN:
        with open("stats.json", 'r') as f:
            stats = json.load(f)

        toremove = []
        for i in stats.get("groups"):
            try:
                bot.send_message(i, ' '.join(args))
                log.info("message sent to group " + str(i))
            except Unauthorized:
                toremove.append(i)
                log.info("couldnt send message to group (unauthorized) " + str(i))
                continue
            except BadRequest:
                toremove.append(i)
                log.info("couldnt send message to group (badrequest) " + str(i))
                continue
        for i in toremove:
            stats.get("groups").remove(i)
        with open("stats.json", 'w') as f:
            json.dump(stats, f)
        bot.send_message(cid, 'Messages sent!')

def command_newgame(bot, update):
    global game
    cid = update.message.chat_id
    grptype = update.message.chat.type
    if grptype == 'group' or grptype == 'supergroup':
        if cid not in games.keys():
            games[cid] = Game(cid, update.message.from_user.id)
            with open("stats.json", 'r') as f:
                stats = json.load(f)
            if cid not in stats.get("groups"):
                stats.get("groups").append(cid)
                with open("stats.json", 'w') as f:
                    json.dump(stats, f)
            bot.send_message(cid,
                             "Neues Spiel erstellt! Jeder Spieler muss mit /join dem Spiel beitreten.\nDer Initiator dieses Spiels (oder der Admin) kann ebenfalls mit /join beitreten und mit /startgame das Spiel starten, sobald alle beigetreten sind!")
        else:
            bot.send_message(cid, "Zur Zeit läuft bereits ein Spiel. Wenn du dieses Spiel beenden möchtest, schreibe /cancelgame!")
    else:
        bot.send_message(cid, "Du musst mich zuerst einer Gruppe hinzufügen und dort /newgame schreiben!")


def command_join(bot, update):
    group_name = update.message.chat.title
    cid = update.message.chat_id
    grptype = update.message.chat.type
    if grptype == 'group' or grptype == 'supergroup':
        if cid in games.keys():
            game = games[cid]
            uid = update.message.from_user.id
            fname = update.message.from_user.first_name
            if game.board is None:  
                if uid not in game.playerlist:
                    if len(game.playerlist) < 10:
                        player = Player(fname, uid)
                        try:
                            bot.send_message(uid,
                                             "Du bist einem Spiel beigetreten in %s. Ich werde dir bald deine geheime Rolle verraten." % group_name)
                            game.add_player(uid, player)
                            if len(game.playerlist) > 4:
                                bot.send_message(game.cid,
                                                 fname + " ist dem Spiel beigetreten. Schreibe /startgame, wenn dies der letzte Spieler war und du das Spiel mit %d Spielern starten möchtest!" % len(
                                                     game.playerlist))
                            else:
                                if len(game.playerlist) == 1:
                                    bot.send_message(game.cid,
                                                     "%s ist dem Spiel beigetreten. Zur Zeit befindet sich %d Spieler im Spiel und man benötigt 5-10 Spieler." % (
                                                         fname, len(game.playerlist)))
                                else:
                                    bot.send_message(game.cid,
                                                     "%s ist dem Spiel beigetreten. Zur Zeit befinden sich %d Spieler im Spiel und man benötigt 5-10 Spieler." % (
                                                         fname, len(game.playerlist)))
                        except Exception:
                            bot.send_message(game.cid,
                                             fname + ", Ich kann dir keine private Nachricht senden. Bitte geh zu @thesecrethöckebot und klicke \"Start\".\nDann musst du erneut /join tippen.")
                    else:
                        bot.send_message(game.cid,
                                         "Du hast die maximale Anzahl an Spielern erreicht. Bitte starte das Spiel mit /startgame!")
                else:
                    bot.send_message(game.cid, "Du bist dem Spiel bereits beigetreten, %s!" % fname)
            else:
                bot.send_message(cid, "Das Spiel hat begonnen. Bitte warte auf das nächste Spiel!")
        else:
            bot.send_message(cid, "In diesem Chat läuft kein Spiel. Bitte erstelle eine neues Spiel mit /newgame")
    else:
        bot.send_message(cid, "Du musst mich zuerst einer Gruppe hinzufügen und dort /newgame tippen!")


def command_startgame(bot, update):
    log.info('command_startgame called')
    cid = update.message.chat_id
    group_name = update.message.chat.title
    if cid in games.keys():
        game = games[cid]
        status = bot.getChatMember(cid, update.message.from_user.id).status
        if game.board is None:
            if update.message.from_user.id == game.initiator or status in ("administrator", "creator"):
                player_number = len(game.playerlist)
                if player_number > 4:
                    inform_players(bot, game, game.cid, player_number)
                    inform_fascists(bot, game, player_number)
                    game.board = Board(player_number, game)
                    game.shuffle_player_sequence()
                    game.board.state.player_counter = 0
                    bot.send_message(game.cid, game.board.print_board())
                    #bot.send_message(ADMIN, "Game of Secret Höcke started in group %s (%d)" % (group_name, cid))
                    start_round(bot, game)
                else:
                    bot.send_message(game.cid, "Nicht genügend Spieler (min. 5, max. 10). Tritt dem Spiel bei mit /join")
            else:
                bot.send_message(game.cid, "Nur der Initiator des Spiels oder ein Gruppenadmin kann das Spiel starten mit /startgame")
        else:
            bot.send_message(cid, "Das Spiel läuft bereits!")
    else:
        bot.send_message(cid, "In diesem Chat läuft kein Spiel. Bitte erstelle eine neues Spiel mit /newgame")


def command_cancelgame(bot, update):
    cid = update.message.chat_id
    if cid in games.keys():
        game = games[cid]
        status = bot.getChatMember(cid, update.message.from_user.id).status
        if update.message.from_user.id == game.initiator or status in ("administrator", "creator"):
            end_game(bot, game, 99)
        else:
            bot.send_message(cid, "Nur der Initiator des Spiels oder ein Gruppenadmin kann das Spiel beenden mit /cancelgame")
    else:
        bot.send_message(cid, "In diesem Chat läuft kein Spiel. Bitte erstelle eine neues Spiel mit /newgame")


##
#
# Beginning of round
#
##

def start_round(bot, game):
    log.info('start_round called')
    if game.board.state.chosen_president is None:
        game.board.state.nominated_president = game.player_sequence[game.board.state.player_counter]
    else:
        game.board.state.nominated_president = game.board.state.chosen_president
        game.board.state.chosen_president = None
    bot.send_message(game.cid,
                     "Der nächste Präsident ist %s.\n%s, bitte nominiere einen Kanzler in unserem privaten Chat!" % (
                         game.board.state.nominated_president.name, game.board.state.nominated_president.name))
    choose_chancellor(bot, game)
    # --> nominate_chosen_chancellor --> vote --> handle_voting --> count_votes --> voting_aftermath --> draw_policies
    # --> choose_policy --> pass_two_policies --> choose_policy --> enact_policy --> start_round


def choose_chancellor(bot, game):
    log.info('choose_chancellor called')
    strcid = str(game.cid)
    pres_uid = 0
    chan_uid = 0
    btns = []
    if game.board.state.president is not None:
        pres_uid = game.board.state.president.uid
    if game.board.state.chancellor is not None:
        chan_uid = game.board.state.chancellor.uid
    for uid in game.playerlist:
        # If there are only five players left in the
        # game, only the last elected Chancellor is
        # ineligible to be Chancellor Candidate; the
        # last President may be nominated.
        if len(game.player_sequence) > 5:
            if uid != game.board.state.nominated_president.uid and game.playerlist[
                uid].is_dead == False and uid != pres_uid and uid != chan_uid:
                name = game.playerlist[uid].name
                btns.append([InlineKeyboardButton(name, callback_data=strcid + "_chan_" + str(uid))])
        else:
            if uid != game.board.state.nominated_president.uid and game.playerlist[
                uid].is_dead == False and uid != chan_uid:
                name = game.playerlist[uid].name
                btns.append([InlineKeyboardButton(name, callback_data=strcid + "_chan_" + str(uid))])

    chancellorMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.nominated_president.uid, game.board.print_board())
    bot.send_message(game.board.state.nominated_president.uid, 'Bitte nominiere deinen Kanzler!',
                     reply_markup=chancellorMarkup)


def nominate_chosen_chancellor(bot, update):
    log.info('nominate_chosen_chancellor called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_chan_([0-9]*)", callback.data)
    cid = int(regex.group(1))
    chosen_uid = int(regex.group(2))
    try:
        game = games[cid]
        game.board.state.nominated_chancellor = game.playerlist[chosen_uid]
        log.info("Präsident %s (%d) nominiert %s (%d)" % (
            game.board.state.nominated_president.name, game.board.state.nominated_president.uid,
            game.board.state.nominated_chancellor.name, game.board.state.nominated_chancellor.uid))
        bot.edit_message_text("Du hast %s als Kanzler nominiert!" % game.board.state.nominated_chancellor.name,
                              callback.from_user.id, callback.message.message_id)
        bot.send_message(game.cid,
                         "Präsident %s hat %s als Kanzler nominiert. Bitte wähle jetzt!" % (
                             game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name))
        vote(bot, game)
    except AttributeError as e:
        log.error("nominate_chosen_chancellor: Game or board should not be None!")
    except Exception as e:
        log.error("Unknown error: " + str(e))


def vote(bot, game):
    log.info('vote called')
    strcid = str(game.cid)
    btns = [[InlineKeyboardButton("Ja", callback_data=strcid + "_Ja"), InlineKeyboardButton("Nein", callback_data=strcid + "_Nein")]]
    voteMarkup = InlineKeyboardMarkup(btns)
    for uid in game.playerlist:
        if not game.playerlist[uid].is_dead:
            if game.playerlist[uid] is not game.board.state.nominated_president:
                # the nominated president already got the board before nominating a chancellor
                bot.send_message(uid, game.board.print_board())
            bot.send_message(uid,
                             "Willst du den Präsidenten %s und Kanzler %s wählen?" % (
                                 game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name),
                             reply_markup=voteMarkup)


def handle_voting(bot, update):
    callback = update.callback_query
    log.info('handle_voting called: %s' % callback.data)
    regex = re.search("(-[0-9]*)_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = regex.group(2)
    try:
        game = games[cid]
        uid = callback.from_user.id
        bot.edit_message_text("Danke für deine Stimme: %s zu Präsident %s und Kanzler %s" % (
            answer, game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name), uid,
                              callback.message.message_id)
        log.info("Spieler %s (%d) stimmt mit %s" % (callback.from_user.first_name, uid, answer))
        if uid not in game.board.state.last_votes:
            game.board.state.last_votes[uid] = answer
        if len(game.board.state.last_votes) == len(game.player_sequence):
            count_votes(bot, game)
    except:
        log.error("handle_voting: Game or board should not be None!")


def count_votes(bot, game):
    log.info('count_votes called')
    voting_text = ""
    voting_success = False
    for player in game.player_sequence:
        if game.board.state.last_votes[player.uid] == "Ja":
            voting_text += game.playerlist[player.uid].name + " stimmt mit Ja!\n"
        elif game.board.state.last_votes[player.uid] == "Nein":
            voting_text += game.playerlist[player.uid].name + " stimmt mit Nein!\n"
    if list(game.board.state.last_votes.values()).count("Ja") > len(
            game.player_sequence) / 2:  # because player_sequence doesnt include dead
        # VOTING WAS SUCCESSFUL
        log.info("Wahl erfolgreich")
        voting_text += "Heil Präsident %s! Heil Kanzler %s!" % (
            game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name)
        game.board.state.chancellor = game.board.state.nominated_chancellor
        game.board.state.president = game.board.state.nominated_president
        game.board.state.nominated_president = None
        game.board.state.nominated_chancellor = None
        voting_success = True
        bot.send_message(game.cid, voting_text)
        voting_aftermath(bot, game, voting_success)
    else:
        log.info("Voting failed")
        voting_text += "Das Volk mochte die beiden Kandidaten nicht!"
        game.board.state.nominated_president = None
        game.board.state.nominated_chancellor = None
        game.board.state.failed_votes += 1
        if game.board.state.failed_votes == 3:
            do_anarchy(bot, game)
        else:
            bot.send_message(game.cid, voting_text)
            voting_aftermath(bot, game, voting_success)


def voting_aftermath(bot, game, voting_success):
    log.info('voting_aftermath called')
    game.board.state.last_votes = {}
    if voting_success:
        if game.board.state.fascist_track >= 3 and game.board.state.chancellor.role == "Höcke":
            # fascists win, because Höcke was elected as chancellor after 3 fascist policies
            game.board.state.game_endcode = -2
            end_game(bot, game, game.board.state.game_endcode)
        elif game.board.state.fascist_track >= 3 and game.board.state.chancellor.role != "Höcke" and game.board.state.chancellor not in game.board.state.not_hitlers:
            game.board.state.not_hitlers.append(game.board.state.chancellor)
            draw_policies(bot, game)
        else:
            # voting was successful and Höcke was not nominated as chancellor after 3 fascist policies
            draw_policies(bot, game)
    else:
        bot.send_message(game.cid, game.board.print_board())
        start_next_round(bot, game)


def draw_policies(bot, game):
    log.info('draw_policies called')
    strcid = str(game.cid)
    game.board.state.veto_refused = False
    # shuffle discard pile with rest if rest < 3
    shuffle_policy_pile(bot, game)
    btns = []
    for i in range(3):
        game.board.state.drawn_policies.append(game.board.policies.pop(0))
    for policy in game.board.state.drawn_policies:
        btns.append([InlineKeyboardButton(policy, callback_data=strcid + "_" + policy)])

    choosePolicyMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.president.uid,
                     "Du hast die folgenden 3 Gesetze gezogen. Welches davon möchtest du verwerfen?",
                     reply_markup=choosePolicyMarkup)


def choose_policy(bot, update):
    log.info('choose_policy called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = regex.group(2)
    try:
        game = games[cid]
        strcid = str(game.cid)
        uid = callback.from_user.id
        if len(game.board.state.drawn_policies) == 3:
            log.info("Spieler %s (%d) verwarf %s" % (callback.from_user.first_name, uid, answer))
            bot.edit_message_text("Das %s wird verworfen!" % answer, uid,
                                  callback.message.message_id)
            # remove policy from drawn cards and add to discard pile, pass the other two policies
            for i in range(3):
                if game.board.state.drawn_policies[i] == answer:
                    game.board.discards.append(game.board.state.drawn_policies.pop(i))
                    break
            pass_two_policies(bot, game)
        elif len(game.board.state.drawn_policies) == 2:
            if answer == "veto":
                log.info("Spieler %s (%d) schlägt ein Veto vor." % (callback.from_user.first_name, uid))
                bot.edit_message_text("Du schlägst dem Präsidenten %s ein Veto vor." % game.board.state.president.name, uid,
                                      callback.message.message_id)
                bot.send_message(game.cid,
                                 "Kanzler %s schlägt dem Preäidenten %s ein Veto vor." % (
                                     game.board.state.chancellor.name, game.board.state.president.name))

                btns = [[InlineKeyboardButton("Veto! (Azkeptiere Vorschlag)", callback_data=strcid + "_yesveto")], [InlineKeyboardButton("Kein Veto! (Vorschlag ablehnen)", callback_data=strcid + "_noveto")]]

                vetoMarkup = InlineKeyboardMarkup(btns)
                bot.send_message(game.board.state.president.uid,
                                 "Kanzler %s schlägt dir ein Veto vor. Möchtest du diese Karten verwerfen?" % game.board.state.chancellor.name,
                                 reply_markup=vetoMarkup)
            else:
                log.info("Spieler %s (%d) wählt ein %s Gesetz" % (callback.from_user.first_name, uid, answer))
                bot.edit_message_text("Ein %s tritt in Kraft!" % answer, uid,
                                      callback.message.message_id)
                # remove policy from drawn cards and enact, discard the other card
                for i in range(2):
                    if game.board.state.drawn_policies[i] == answer:
                        game.board.state.drawn_policies.pop(i)
                        break
                game.board.discards.append(game.board.state.drawn_policies.pop(0))
                assert len(game.board.state.drawn_policies) == 0
                enact_policy(bot, game, answer, False)
        else:
            log.error("choose_policy: drawn_policies should be 3 or 2, but was " + str(
                len(game.board.state.drawn_policies)))
    except:
        log.error("choose_policy: Game or board should not be None!")


def pass_two_policies(bot, game):
    log.info('pass_two_policies called')
    strcid = str(game.cid)
    btns = []
    for policy in game.board.state.drawn_policies:
        btns.append([InlineKeyboardButton(policy, callback_data=strcid + "_" + policy)])
    if game.board.state.fascist_track == 5 and not game.board.state.veto_refused:
        btns.append([InlineKeyboardButton("Veto", callback_data=strcid + "_veto")])
        choosePolicyMarkup = InlineKeyboardMarkup(btns)
        bot.send_message(game.cid,
                         "Präsident %s gab zwei Gesetze an Kanzler %s." % (
                             game.board.state.president.name, game.board.state.chancellor.name))
        bot.send_message(game.board.state.chancellor.uid,
                         "Präsident %s gab dir die folgenden zwei Gesetze. Welches davon möchtes du verabschieden? Du kannst auch dein Veto-Recht nutzen." % game.board.state.president.name,
                         reply_markup=choosePolicyMarkup)
    elif game.board.state.veto_refused:
        choosePolicyMarkup = InlineKeyboardMarkup(btns)
        bot.send_message(game.board.state.chancellor.uid,
                         "Präsident %s hat dein Veto abgelehnt. Du musst dich entscheiden. Welches Gesetz möchtes du verabschieden?" % game.board.state.president.name,
                         reply_markup=choosePolicyMarkup)
    elif game.board.state.fascist_track < 5:
        choosePolicyMarkup = InlineKeyboardMarkup(btns)
        bot.send_message(game.board.state.chancellor.uid,
                         "Präsident %s gab dir die folgenden zwei Gesetze. Welches davon möchtes du verabschieden?" % game.board.state.president.name,
                         reply_markup=choosePolicyMarkup)


def enact_policy(bot, game, policy, anarchy):
    log.info('enact_policy called')
    if policy == "Gesetz der extremen Mitte":
        game.board.state.liberal_track += 1
    elif policy == "Gesetz der Faschisten":
        game.board.state.fascist_track += 1
    game.board.state.failed_votes = 0  # reset counter
    if not anarchy:
        bot.send_message(game.cid,
                         "Präsident %s und Kanzler %s verabschieden ein %s!" % (
                             game.board.state.president.name, game.board.state.chancellor.name, policy))
    else:
        bot.send_message(game.cid,
                         "Das oberste Gesetz wird verabschiedet: %s" % policy)
    sleep(3)
    bot.send_message(game.cid, game.board.print_board())
    # end of round
    if game.board.state.liberal_track == 5:
        game.board.state.game_endcode = 1
        end_game(bot, game, game.board.state.game_endcode)  # liberals win with 5 liberal policies
    if game.board.state.fascist_track == 6:
        game.board.state.game_endcode = -1
        end_game(bot, game, game.board.state.game_endcode)  # fascists win with 6 fascist policies
    sleep(3)
    if not anarchy:
        if policy == "Gesetz der Faschisten":
            action = game.board.fascist_track_actions[game.board.state.fascist_track - 1]
            if action is None and game.board.state.fascist_track == 6:
                pass
            elif action == None:
                start_next_round(bot, game)
            elif action == "policy":
                bot.send_message(game.cid,
                                 "Präsidialmacht in Kraft gesetzt: Vorschau auf Gesetze " + u"\U0001F52E" + "\nPräsident " + game.board.state.president.name + " kennt nun die nächsten 3 Gesetze auf "
                                                                                                                                                 "dem Stapel. Der Präsident kann seine Erkenntnisse "
                                                                                                                                                 "mit den anderen Spielern teilen (oder sie belügen!) "
                                                                                                                                                 "oder sie für sich behalten.")
                action_policy(bot, game)
            elif action == "kill":
                bot.send_message(game.cid,
                                 "Präsidialmacht in Kraft gesetzt: Hinrichtung " + u"\U0001F5E1" + "\nPräsident " + game.board.state.president.name + " muss eine Person töten. Ihr könnt "
                                                                                                                                               "über die Entscheidung diskutieren, aber "
                                                                                                                                               "der Präsident hat den Finger am Abzug.")
                action_kill(bot, game)
            elif action == "inspect":
                bot.send_message(game.cid,
                                 "Präsidialmacht in Kraft gesetzt: Gesinnung untersuchen " + u"\U0001F50E" + "\nPräsident " + game.board.state.president.name + " kann die Gesinnung eines anderen "
                                                                                                                                                         "Spielers sehen. Der Präsident kann keine "
                                                                                                                                                         "Erkenntnisse mit den anderen Spielern teilen "
                                                                                                                                                         "(oder sie belügen!) oder sie für sich behalten.")
                action_inspect(bot, game)
            elif action == "choose":
                bot.send_message(game.cid,
                                 "Präsidialmacht in Kraft gesetzt: Spezielle Präsidentschaftswahl " + u"\U0001F454" + "\nPräsident " + game.board.state.president.name + " darf den nächsten Präsidenten "
                                                                                                                                                           "bestimmen. Danach geht die Reihenfolge wieder normal weiter."

                action_choose(bot, game)
        else:
            start_next_round(bot, game)
    else:
        start_next_round(bot, game)


def choose_veto(bot, update):
    log.info('choose_veto called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = regex.group(2)
    try:
        game = games[cid]
        uid = callback.from_user.id
        if answer == "yesveto":
            log.info("Spieler %s (%d) accepted the veto" % (callback.from_user.first_name, uid))
            bot.edit_message_text("Du akzeptierst das Veto!", uid, callback.message.message_id)
            bot.send_message(game.cid,
                             "Präsident %s akzeptiert Kanzler %s's Veto. Es wird kein Gesetz verabschiedet, doch die Wahl zählt als fehlgeschlagen." % (
                                 game.board.state.president.name, game.board.state.chancellor.name))
            game.board.discards += game.board.state.drawn_policies
            game.board.state.drawn_policies = []
            game.board.state.failed_votes += 1
            if game.board.state.failed_votes == 3:
                do_anarchy(bot, game)
            else:
                bot.send_message(game.cid, game.board.print_board())
                start_next_round(bot, game)
        elif answer == "noveto":
            log.info("Player %s (%d) declined the veto" % (callback.from_user.first_name, uid))
            game.board.state.veto_refused = True
            bot.edit_message_text("Du hast das Veto abgelehnt!", uid, callback.message.message_id)
            bot.send_message(game.cid,
                             "Präsident %s lehnt Kanzler %s's Veto ab. Der Kanzler muss nun ein Gesetz auswählen!" % (
                                 game.board.state.president.name, game.board.state.chancellor.name))
            pass_two_policies(bot, game)
        else:
            log.error("choose_veto: Callback data can either be \"veto\" or \"noveto\", but not %s" % answer)
    except:
        log.error("choose_veto: Game or board should not be None!")


def do_anarchy(bot, game):
    log.info('do_anarchy called')
    bot.send_message(game.cid, game.board.print_board())
    bot.send_message(game.cid, "ANARCHIE!!")
    top_policy = game.board.policies.pop(0)
    game.board.state.last_votes = {}
    enact_policy(bot, game, top_policy, True)


def action_policy(bot, game):
    log.info('action_policy called')
    topPolicies = ""
    # shuffle discard pile with rest if rest < 3
    shuffle_policy_pile(bot, game)
    for i in range(3):
        topPolicies += game.board.policies[i] + "\n"
    bot.send_message(game.board.state.president.uid,
                     "Die oberen drei Gesetze sind (oberstes zuerst):\n%s\nDu darfst deine Mitspieler belügen." % topPolicies)
    start_next_round(bot, game)


def action_kill(bot, game):
    log.info('action_kill called')
    strcid = str(game.cid)
    btns = []
    for uid in game.playerlist:
        if uid != game.board.state.president.uid and game.playerlist[uid].is_dead == False:
            name = game.playerlist[uid].name
            btns.append([InlineKeyboardButton(name, callback_data=strcid + "_kill_" + str(uid))])

    killMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.president.uid, game.board.print_board())
    bot.send_message(game.board.state.president.uid,
                     'Du musst einen Spieler erschießen. Du kannst deine Entschiedung mit den anderen Spielern diskutieren. Entscheide dich weise!',
                     reply_markup=killMarkup)


def choose_kill(bot, update):
    log.info('choose_kill called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_kill_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = int(regex.group(2))
    try:
        game = games[cid]
        chosen = game.playerlist[answer]
        chosen.is_dead = True
        if game.player_sequence.index(chosen) <= game.board.state.player_counter:
            game.board.state.player_counter -= 1
        game.player_sequence.remove(chosen)
        game.board.state.dead += 1
        log.info("Player %s (%d) killed %s (%d)" % (
            callback.from_user.first_name, callback.from_user.id, chosen.name, chosen.uid))
        bot.edit_message_text("Du hast %s erschossen!" % chosen.name, callback.from_user.id, callback.message.message_id)
        if chosen.role == "Höcke":
            bot.send_message(game.cid, "Präsident " + game.board.state.president.name + " erschießt " + chosen.name + ". ")
            end_game(bot, game, 2)
        else:
            bot.send_message(game.cid,
                             "Präsident %s erschießt %s, welcher nicht Höcke war. %s, du bist nun tot und darfst nicht mehr sprechen!" % (
                                 game.board.state.president.name, chosen.name, chosen.name))
            bot.send_message(game.cid, game.board.print_board())
            start_next_round(bot, game)
    except:
        log.error("choose_kill: Game or board should not be None!")


def action_choose(bot, game):
    log.info('action_choose called')
    strcid = str(game.cid)
    btns = []

    for uid in game.playerlist:
        if uid != game.board.state.president.uid and game.playerlist[uid].is_dead == False:
            name = game.playerlist[uid].name
            btns.append([InlineKeyboardButton(name, callback_data=strcid + "_choo_" + str(uid))])

    inspectMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.president.uid, game.board.print_board())
    bot.send_message(game.board.state.president.uid,
                     'Du darfst den nächsten Präsidenten bestimmen. Danach ist die Reihenfolge wieder wie normal. Entscheide dich weise!',
                     reply_markup=inspectMarkup)


def choose_choose(bot, update):
    log.info('choose_choose called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_choo_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = int(regex.group(2))
    try:
        game = games[cid]
        chosen = game.playerlist[answer]
        game.board.state.chosen_president = chosen
        log.info(
            "Spieler %s (%d) bestimmt %s (%d) als nächsten Präsidenten" % (
                callback.from_user.first_name, callback.from_user.id, chosen.name, chosen.uid))
        bot.edit_message_text("Du bestimmst %s als den nächsten Präsidenten!" % chosen.name, callback.from_user.id,
                              callback.message.message_id)
        bot.send_message(game.cid,
                         "Präsident %s bestimmt %s als den nächsten Präsidenten." % (
                             game.board.state.president.name, chosen.name))
        start_next_round(bot, game)
    except:
        log.error("choose_choose: Game or board should not be None!")


def action_inspect(bot, game):
    log.info('action_inspect called')
    strcid = str(game.cid)
    btns = []
    for uid in game.playerlist:
        if uid != game.board.state.president.uid and game.playerlist[uid].is_dead == False:
            name = game.playerlist[uid].name
            btns.append([InlineKeyboardButton(name, callback_data=strcid + "_insp_" + str(uid))])

    inspectMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.president.uid, game.board.print_board())
    bot.send_message(game.board.state.president.uid,
                     'Du darfst die Gesinnung eines anderen Spielers sehen. Wen wählst du aus? Entscheide dich weise!',
                     reply_markup=inspectMarkup)


def choose_inspect(bot, update):
    log.info('choose_inspect called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_insp_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = int(regex.group(2))
    try:
        game = games[cid]
        chosen = game.playerlist[answer]
        log.info(
            "Player %s (%d) inspects %s (%d)'s party membership (%s)" % (
                callback.from_user.first_name, callback.from_user.id, chosen.name, chosen.uid,
                chosen.party))
        bot.edit_message_text("Die Gesinnung von %s ist %s" % (chosen.name, chosen.party),
                              callback.from_user.id,
                              callback.message.message_id)
        bot.send_message(game.cid, "Präsident %s untersucht %s." % (game.board.state.president.name, chosen.name))
        start_next_round(bot, game)
    except:
        log.error("choose_inspect: Game or board should not be None!")


def start_next_round(bot, game):
    log.info('start_next_round called')
    # start next round if there is no winner (or /cancel)
    if game.board.state.game_endcode == 0:
        # start new round
        sleep(5)
        # if there is no special elected president in between
        if game.board.state.chosen_president is None:
            increment_player_counter(game)
        start_round(bot, game)


##
#
# End of round
#
##

def end_game(bot, game, game_endcode):
    log.info('end_game called')
    ##
    # game_endcode:
    #   -2  fascists win by electing Höcke as chancellor
    #   -1  fascists win with 6 fascist policies
    #   0   not ended
    #   1   liberals win with 5 liberal policies
    #   2   liberals win by killing Höcke
    #   99  game cancelled
    #
    with open("stats.json", 'r') as f:
        stats = json.load(f)

    if game_endcode == 99:
        if games[game.cid].board is not None:
            bot.send_message(game.cid,
                             "Spiel beendet!\n\n%s" % game.print_roles())
            #bot.send_message(ADMIN, "Game of Secret Höcke canceled in group %d" % game.cid)
            stats['cancelled'] = stats['cancelled'] + 1
        else:
            bot.send_message(game.cid, "Game beendet!")
    else:
        if game_endcode == -2:
            bot.send_message(game.cid,
                             "Game over! Die Faschisten gewinnen, indem Höcke zum Kanzler gewählt wurde!\n\n%s" % game.print_roles())
            stats['fascwin_hitler'] = stats['fascwin_hitler'] + 1
        if game_endcode == -1:
            bot.send_message(game.cid,
                             "Game over! Die Faschisten gewinnen, indem sie 6 faschistische Gesetze verabschiedet haben!\n\n%s" % game.print_roles())
            stats['fascwin_policies'] = stats['fascwin_policies'] + 1
        if game_endcode == 1:
            bot.send_message(game.cid,
                             "Game over! Die PARTEI-Genossinnen gewinnen, indem sie 5 Gesetze der extremen Mitte verabschiedet haben!\n\n%s" % game.print_roles())
            stats['libwin_policies'] = stats['libwin_policies'] + 1
        if game_endcode == 2:
            bot.send_message(game.cid,
                             "Game over! Die PARTEI-Genossinnen gewinnen, indem sie Bernd Höcke erschossen haben! FCK AFD!\n\n%s" % game.print_roles())
            stats['libwin_kill'] = stats['libwin_kill'] + 1

        #bot.send_message(ADMIN, "Game of Secret Höcke ended in group %d" % game.cid)

    with open("stats.json", 'w') as f:
        json.dump(stats, f)
    del games[game.cid]


def inform_players(bot, game, cid, player_number):
    log.info('inform_players called')
    bot.send_message(cid,
                     "Lass uns das Spiel starten mit %d Spielern!\n%s\nGehe zu deinem privaten Chat und schaue dir deine geheime Rolle an!" % (
                         player_number, print_player_info(player_number)))
    available_roles = list(players[player_number]["roles"])  # copy not reference because we need it again later
    for uid in game.playerlist:
        random_index = randrange(len(available_roles))
        role = available_roles.pop(random_index)
        party = get_membership(role)
        game.playerlist[uid].role = role
        game.playerlist[uid].party = party
        bot.send_message(uid, "Deine geheime Rolle ist: %s\nDeine Gesinnung ist %s" % (role, party))


def print_player_info(player_number):
    if player_number == 5:
        return "Es gibt 3 PARTEI-Genossinnen, 1 Faschist und Bernd Höcke. Höcke weiß, wer der andere Faschist ist."
    elif player_number == 6:
        return "There are 4 PARTEI-Genossinnen, 1 Faschist und Bernd Höcke. Höcke wer der andere Faschist ist."
    elif player_number == 7:
        return "There are 4 PARTEI-Genossinnen, 2 Faschisten und Bernd Höcke. Höcke weiß nicht, wer die Faschisten sind."
    elif player_number == 8:
        return "There are 5 PARTEI-Genossinnen, 2 Faschisten und Bernd Höcke. Höcke weiß nicht, wer die Faschisten sind."
    elif player_number == 9:
        return "There are 5 PARTEI-Genossinnen, 3 Faschisten und Bernd Höcke. Höcke weiß nicht, wer die Faschisten sind."
    elif player_number == 10:
        return "There are 6 PARTEI-Genossinnen, 3 Faschisten und Bernd Höcke. Höcke weiß nicht, wer die Faschisten sind."


def inform_fascists(bot, game, player_number):
    log.info('inform_fascists called')
    if player_number == 5 or player_number == 6:
        for uid in game.playerlist:
            role = game.playerlist[uid].role
            if role == "Höcke":
                fascists = game.get_fascists()
                if len(fascists) > 1:
                    bot.send_message(uid, "Fehler. Es sollte nur einen Faschisten geben in einem Spiel mit 5/6 Spielern!")
                else:
                    bot.send_message(uid, "Dein verbündeter Faschist ist: %s" % fascists[0].name)
            elif role == "Faschist":
                hitler = game.get_hitler()
                bot.send_message(uid, "Höcke ist: %s" % hitler.name)
            elif role == "PARTEI-Genossin":
                pass
            else:
                log.error("inform_fascists: can\'t handle the role %s" % role)

    else:
        for uid in game.playerlist:
            role = game.playerlist[uid].role
            if role == "Faschist":
                fascists = game.get_fascists()
                if len(fascists) == 1:
                    bot.send_message(uid, "Fehler: Es sollte mehr als einen Faschisten geben in einem Spiel mit 7/8/9/10 Spielern!")
                else:
                    fstring = ""
                    for f in fascists:
                        if f.uid != uid:
                            fstring += f.name + ", "
                    fstring = fstring[:-2]
                    bot.send_message(uid, "Deine verbündeten Faschisten sind: %s" % fstring)
                    hitler = game.get_hitler()
                    bot.send_message(uid, "Höcke ist: %s" % hitler.name)
            elif role == "Höcke":
                pass
            elif role == "PARTEI-Genossin":
                pass
            else:
                log.error("inform_fascists: can\'t handle the role %s" % role)


def get_membership(role):
    log.info('get_membership called')
    if role == "Faschist" or role == "Höcke":
        return "faschistisch"
    elif role == "PARTEI-Genossin":
        return "extreme Mitte"
    else:
        return None


def increment_player_counter(game):
    log.info('increment_player_counter called')
    if game.board.state.player_counter < len(game.player_sequence) - 1:
        game.board.state.player_counter += 1
    else:
        game.board.state.player_counter = 0


def shuffle_policy_pile(bot, game):
    log.info('shuffle_policy_pile called')
    if len(game.board.policies) < 3:
        game.board.discards += game.board.policies
        game.board.policies = random.sample(game.board.discards, len(game.board.discards))
        game.board.discards = []
        bot.send_message(game.cid,
                         "Es lagen nicht mehr genug Karten auf dem Gesetze-Stapel, also habe ich den Rest mit dem Ablagestapel vermischt!")


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def main():
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", command_start))
    dp.add_handler(CommandHandler("help", command_help))
    dp.add_handler(CommandHandler("board", command_board))
    dp.add_handler(CommandHandler("rules", command_rules))
    dp.add_handler(CommandHandler("ping", command_ping))
    dp.add_handler(CommandHandler("symbols", command_symbols))
    dp.add_handler(CommandHandler("stats", command_stats))
    dp.add_handler(CommandHandler("reboot", command_reboot))
    dp.add_handler(CommandHandler("newgame", command_newgame))
    dp.add_handler(CommandHandler("startgame", command_startgame))
    dp.add_handler(CommandHandler("cancelgame", command_cancelgame))
    dp.add_handler(CommandHandler("broadcast", command_broadcast, pass_args=True))
    dp.add_handler(CommandHandler("join", command_join))

    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_chan_(.*)", callback=nominate_chosen_chancellor))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_insp_(.*)", callback=choose_inspect))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_choo_(.*)", callback=choose_choose))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_kill_(.*)", callback=choose_kill))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_(yesveto|noveto)", callback=choose_veto))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_(liberal|fascist|veto)", callback=choose_policy))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_(Ja|Nein)", callback=handle_voting))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
