"""
The exporter's messages (errors, warnings, info) and the unfinished work it leaves out.
"""

from typing import List

import bpy

# Rather than a "did_print_once"
#
# This is yet another reminder about how relying on strings printed to a console
# To tell how your unit test went is a bad idea, especially when you can't seem to control
# What gets output when.
_printed = [0]

# The text in the .blend that holds the log of the last export
LOG_NAME = "X-Plane Export.log"

"""
Logging Style Guide:
    - Put the name of object or source of error first, leave a trail to follow quickly
    - Include how to correct a problem instead of simply complaining about it, if possible
    - Simple English benefits all, no programmer speak, mentions of the API, or complex grammar
    - Be clear when you're talking about Blender concepts and X-Plane concepts
    - Be terse, avoid more than a sentence including data filled in strings - avoid word wrapping
    - Speak calmly and positively. Avoid "you failed" statements and exclamation marks
    - One error per problem, not one error per newline
    - Find errors whenever possible during the collection phase instead of writing the writing phase
    - Test errors are emitted as part of unit testing

Spending 20mins on a good error message is better than 2hrs troubleshooting an author's
non-existant bug
"""


class XPlaneLogger:
    def __init__(self):
        self.transports = []
        self.messages = []

    def addTransport(
        self, transport, messageTypes=["error", "warning", "info", "success"]
    ):
        self.transports.append({"fn": transport, "types": messageTypes})

    def clear(self):
        self.clearTransports()
        self.clearMessages()

    def clearTransports(self):
        del self.transports[:]

    def clearMessages(self):
        del self.messages[:]

    def messagesToString(self, messages=None):
        if messages == None:
            messages = self.messages

        out = ""

        for message in messages:
            out += (
                XPlaneLogger.messageToString(
                    message["type"], message["message"], message["context"]
                )
                + "\n"
            )

        return out

    def log(self, messageType, message, context=None):
        self.messages.append(
            {"type": messageType, "message": message, "context": context}
        )

        for transport in self.transports:
            if messageType in transport["types"]:
                transport["fn"](messageType, message, context)

    def error(self, message, context=None):
        self.log("error", message, context)

    def warn(self, message, context=None):
        self.log("warning", message, context)

    def info(self, message, context=None):
        self.log("info", message, context)

    def success(self, message, context=None):
        self.log("success", message, context)

    def findOfType(self, messageType):
        messages = []

        for message in self.messages:
            if message["type"] == messageType:
                messages.append(message)

        return messages

    def hasOfType(self, messageType):
        for message in self.messages:
            if message["type"] == messageType:
                return True

        return False

    def findErrors(self):
        return self.findOfType("error")

    def hasErrors(self):
        return self.hasOfType("error")

    def errorCount(self) -> int:
        """Lets a step check for errors of its own, ignoring earlier files in the same export"""
        return len(self.findErrors())

    def findWarnings(self):
        return self.findOfType("warning")

    def hasWarnings(self):
        return self.hasOfType("warning")

    def findInfos(self):
        return self.findOfType("info")

    @staticmethod
    def messageToString(messageType, message, context=None):
        _printed[0] += 1
        return "%s: %s" % (messageType.upper(), message)

    @staticmethod
    def InternalTextTransport(name=LOG_NAME):
        if bpy.data.texts.find(name) == -1:
            log = bpy.data.texts.new(name)
        else:
            log = bpy.data.texts[name]

        log.clear()

        def transport(messageType, message, context=None):
            log.write(
                XPlaneLogger.messageToString(messageType, message, context) + "\n"
            )

        return transport

    @staticmethod
    def ConsoleTransport():
        def transport(messageType, message, context=None):
            if _printed[0] == 1:
                print("\n")
            print(XPlaneLogger.messageToString(messageType, message, context))

        return transport

    @staticmethod
    def FileTransport(filehandle):
        def transport(messageType, message, context=None):
            filehandle.write(
                XPlaneLogger.messageToString(messageType, message, context) + "\n"
            )

        return transport


logger = XPlaneLogger()


class UnfinishedWork:
    """
    Settings an author has started but not filled in yet, such as a light level without a dataref.
    Exporting work in progress is normal, so they are left out of the OBJ and counted for the export summary
    instead of being errors that stop the export
    """

    def __init__(self):
        self.items = {}  # type: Dict[str, List[str]]

    def clear(self) -> None:
        self.items.clear()

    def add(self, what: str, name: str) -> None:
        """what is plural, as the summary shows it after the count: 'light levels without a dataref'"""
        names = self.items.setdefault(what, [])
        if name not in names:
            names.append(name)

    def summary(self) -> str:
        return ", ".join(f"{len(names)} {what}" for what, names in self.items.items())

    def details(self) -> List[str]:
        return [
            f"{what}: {', '.join(sorted(names))}" for what, names in self.items.items()
        ]


unfinished = UnfinishedWork()
