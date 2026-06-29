// SPDX-License-Identifier: GPL-2.0

#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/moduleparam.h>

static int count = 3;
module_param(count, int, 0644);
MODULE_PARM_DESC(count, "greet を何回繰り返すか");

static char *who = "world";
module_param(who, charp, 0644);
MODULE_PARM_DESC(who, "誰に挨拶するか");

static int lkm_hello_greet(const int n)
{
	int sum = 0;

	for (int i = 0; i < n; i++) {
		pr_info("lkm_hello: hello %s (%d/%d)\n", who, i + 1, n);
		sum += i;
	}
	return sum;
}

// echo 1 | sudo tee /sys/module/lkm_hello/parameters/trigger
static int trigger_set(const char *val, const struct kernel_param *kp)
{
	int ret = lkm_hello_greet(count);

	pr_info("lkm_hello: trigger -> greet() returned %d\n", ret);
	return 0;
}

static const struct kernel_param_ops trigger_ops = {
	.set = trigger_set,
};
module_param_cb(trigger, &trigger_ops, NULL, 0220);
MODULE_PARM_DESC(trigger, "何か書き込むと lkm_hello_greet() を呼ぶ");

static int __init lkm_hello_init(void)
{
	int ret;

	pr_info("lkm_hello: init (count=%d who=%s)\n", count, who);
	ret = lkm_hello_greet(count);
	pr_info("lkm_hello: init greet() returned %d\n", ret);
	return 0;
}

static void __exit lkm_hello_exit(void)
{
	pr_info("lkm_hello: exit\n");
}

module_init(lkm_hello_init);
module_exit(lkm_hello_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Wataru Ashihara");
MODULE_DESCRIPTION("Minimal LKM as a gdb debugging target (vng + lx-symbols)");
