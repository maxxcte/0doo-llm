/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { one } from '@mail/model/model_field'; 
import { _t } from "@web/core/l10n/translation";
import { clear } from '@mail/model/model_field_command';

// 1. Patch MessageActionList to add compute fields for our custom actions
registerPatch({
    name: 'MessageActionList',
    fields: {
        actionThumbUp: one('MessageAction', {
            compute() {
                // Reverted condition based on last successful state - show for assistant messages
                if (this.message) {
                    return {};
                }
                return clear();
            },
            inverse: 'messageActionListOwnerAsThumbUp',
        }),
        actionThumbDown: one('MessageAction', {
            compute() {
                // Reverted condition based on last successful state - show for assistant messages
                 if (this.message) {
                    return {};
                }
                return clear();
            },
            inverse: 'messageActionListOwnerAsThumbDown',
        }),
    },
});

// 2. Patch MessageAction for correct owner computation and sequence
registerPatch({
    name: 'MessageAction',
    fields: {
         // === New fields (inverse relations) ===
        messageActionListOwnerAsThumbUp: one('MessageActionList', {
            identifying: true,
            inverse: 'actionThumbUp',
        }),
        messageActionListOwnerAsThumbDown: one('MessageActionList', {
            identifying: true,
            inverse: 'actionThumbDown',
        }),

        // === Patched fields ===

        messageActionListOwner: { 
            compute() {
                // Check our custom inverse relations first
                if (this.messageActionListOwnerAsThumbUp) {
                    return this.messageActionListOwnerAsThumbUp;
                }
                if (this.messageActionListOwnerAsThumbDown) {
                    return this.messageActionListOwnerAsThumbDown;
                }
                // If not our actions, call the original compute logic
                return this._super();
            }
        },

        sequence: { 
            compute() {
                 if (this.messageActionListOwnerAsThumbUp) {
                     return 15;
                 }
                 if (this.messageActionListOwnerAsThumbDown) {
                     return 16;
                 }
                 return this._super();
            },
        },
    },
});

// 3. Patch MessageActionView for visual representation AND CLICK HANDLING
registerPatch({
    name: 'MessageActionView',
    fields: {
        classNames: { 
            compute() {
                const messageAction = this.messageAction;
                if (!messageAction) return '';

                if (messageAction.messageActionListOwnerAsThumbUp) {
                    const message = messageAction.messageActionListOwnerAsThumbUp.message;
                    const isVoted = message && message.user_vote === 1;
                    // Use outlined icon if not voted, solid + color if voted
                    const iconClass = isVoted ? 'fa-thumbs-up text-primary fw-bold' : 'fa-thumbs-o-up';
                    return `${this.paddingClassNames} fa fa-lg ${iconClass}`;
                }
                if (messageAction.messageActionListOwnerAsThumbDown) {
                    const message = messageAction.messageActionListOwnerAsThumbDown.message;
                    const isVoted = message && message.user_vote === -1;
                     // Use outlined icon if not voted, solid + color if voted
                    const iconClass = isVoted ? 'fa-thumbs-down text-primary fw-bold' : 'fa-thumbs-o-down';
                    return `${this.paddingClassNames} fa fa-lg ${iconClass}`;
                }

                // If not our actions, call the original compute
                // This will handle core icons (delete, edit, star, etc.) AND padding.
                return this._super();
            }
        },
        title: { 
             compute() {
                 const messageAction = this.messageAction;
                 if (!messageAction) return '';

                 if (messageAction.messageActionListOwnerAsThumbUp) {
                     return _t("Thumb Up");
                 }
                 if (messageAction.messageActionListOwnerAsThumbDown) {
                     return _t("Thumb Down");
                 }
                 // Let original handle others (delete, edit, star, etc.)
                 return this._super();
             }
        }
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
                newVote = currentVote === 1 ? 0 : 1; // Toggle logic
                voteValue = 1;
                isVoteAction = true;
            } else if (messageAction.messageActionListOwnerAsThumbDown) {
                message = messageAction.messageActionListOwnerAsThumbDown.message;
                if (!message) return;
                currentVote = message.user_vote;
                newVote = currentVote === -1 ? 0 : -1; // Toggle logic
                voteValue = -1;
                isVoteAction = true;
            }

            // If it was a vote action, perform the RPC
            if (isVoteAction) {
                try {
                    await this.messaging.rpc({
                        route: "/llm/message/vote",
                        params: {
                            message_id: message.id,
                            vote_value: newVote,
                        },
                    });
                    // Update local state immediately for responsiveness
                    message.update({ user_vote: newVote });
                } catch (error) {
                    console.error(`Error voting ${voteValue === 1 ? 'up' : 'down'}:`, error);
                    // Use notification service if available
                    if (this.env && this.env.services.notification) {
                        this.env.services.notification.add(_t("Failed to record vote."), { type: 'danger' });
                    } else {
                         console.warn("Notification service not available to display vote failure.");
                    }
                    // Optionally revert local state on error, or leave it optimistic
                    // message.update({ user_vote: currentVote }); // Example revert
                }
            } else {
                // Not our action, let the original onClick handle it
                this._super(ev);
            }
        }
    }
});
