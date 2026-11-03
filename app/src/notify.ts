import * as Notifications from 'expo-notifications';
import type { Copy } from './copy';

// Local only: the phone schedules its own reminder, so there's no push server and no device token.
// The text never holds a view or anything anyone said.

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export async function askToNotify(): Promise<boolean> {
  const now = await Notifications.getPermissionsAsync();
  if (now.granted) return true;
  if (!now.canAskAgain) return false;
  const asked = await Notifications.requestPermissionsAsync({
    ios: { allowAlert: true, allowSound: false, allowBadge: false },
  });
  return asked.granted;
}

// Once a day at most, in the early evening.
export async function notifyDaily(copy: Copy): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
  const content = { title: 'Demos', body: copy.notifyText };
  await Notifications.scheduleNotificationAsync({
    content,
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DAILY, hour: 18, minute: 0 },
  });
  if (__DEV__) {
    // Dev builds also send one a few seconds later, so the banner can be checked without waiting a day.
    await Notifications.scheduleNotificationAsync({
      content,
      trigger: { type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL, seconds: 6 },
    });
  }
}

export const stopNotifying = () => Notifications.cancelAllScheduledNotificationsAsync();
