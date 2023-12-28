/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";
import { _t } from "@web/core/l10n/translation";

// 3. Patch MessageActionView for visual representation AND CLICK HANDLING
registerPatch({
  name: "MessageActionView",
  fields: {
    classNames: {
      compute() {
        const messageAction = this.messageAction;
        if (!messageAction) return "";

        if (messageAction.messageActionListOwnerAsThumbUp) {
          const message = messageAction.messageActionListOwnerAsThumbUp.message;
          const isVoted = message && message.user_vote === 1;
          // Use outlined icon if not voted, solid + color if voted
          const iconClass = isVoted
            ? "fa-thumbs-up text-primary fw-bold"
            : "fa-thumbs-o-up";
          return `${this.paddingClassNames} fa fa-lg ${iconClass}`;
        }
        if (messageAction.messageActionListOwnerAsThumbDown) {
          const message =
            messageAction.messageActionListOwnerAsThumbDown.message;
          const isVoted = message && message.user_vote === -1;
          // Use outlined icon if not voted, solid + color if voted
          const iconClass = isVoted
            ? "fa-thumbs-down text-primary fw-bold"
            : "fa-thumbs-o-down";
          return `${this.paddingClassNames} fa fa-lg ${iconClass}`;
        }

        // If not our actions, call the original compute
        // This will handle core icons (delete, edit, star, etc.) AND padding.
        return this._super();
      },
    },
    title: {
      compute() {
        const messageAction = this.messageAction;
        if (!messageAction) return "";

        if (messageAction.messageActionListOwnerAsThumbUp) {
          return _t("Thumb Up");
        }
        if (messageAction.messageActionListOwnerAsThumbDown) {
          return _t("Thumb Down");
        }
        // Let original handle others (delete, edit, star, etc.)
        return this._super();
      },
    },
  },
  recordMethods: {
    async onClick(ev) {
      const messageAction = this.messageAction;
      if (!messageAction) return; // Safety check

      let message, currentVote, newVote, voteValue;
      let isVoteAction = false;

      // Check if it's our thumb actions
      if (messageAction.messageActionListOwnerAsThumbUp) {
        message = messageAction.messageActionListOwnerAsThumbUp.message;
        if (!message) return;
        currentVote = message.user_vote;
        newVote = currentVote === 1 ? 0 : 1;
        voteValue = 1;
        isVoteAction = true;
      } else if (messageAction.messageActionListOwnerAsThumbDown) {
        message = messageAction.messageActionListOwnerAsThumbDown.message;
        if (!message) return;
        currentVote = message.user_vote;
        newVote = currentVote === -1 ? 0 : -1;
        voteValue = -1;
        isVoteAction = true;
      }

      // If it was a vote action, perform the RPC
      if (isVoteAction) {
        try {
          const result = await this.messaging.rpc({
            route: "/llm/message/vote",
            params: {
              message_id: message.id,
              vote_value: newVote,
            },
          });
          if (result.error) {
            throw new Error(result.error);
          }
          message.update({ user_vote: newVote });
        } catch (error) {
          console.error(
            `Error voting ${voteValue === 1 ? "up" : "down"}:`,
            error
          );
          if (this.env && this.env.services.notification) {
            this.env.services.notification.add(
              _t("Failed to record vote. " + error),
              { type: "danger" }
            );
          } else {
            console.warn(
              "Notification service not available to display vote failure."
            );
          }
          message.update({ user_vote: currentVote });
        }
      } else {
        // Not our action, let the original onClick handle it
        this._super(ev);
      }
    },
  },
});
