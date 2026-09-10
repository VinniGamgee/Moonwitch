// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <condition_variable>
#include <mutex>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "common/thread_worker.h"

TEST_CASE("ThreadWorker prioritizes latency-sensitive work", "[common]") {
    Common::ThreadWorker worker{1, "PriorityTest"};
    std::mutex mutex;
    std::condition_variable condition;
    bool gate_started{};
    bool gate_open{};
    std::vector<int> execution_order;

    worker.QueueWork([&] {
        std::unique_lock lock{mutex};
        gate_started = true;
        condition.notify_one();
        condition.wait(lock, [&] { return gate_open; });
    });

    {
        std::unique_lock lock{mutex};
        condition.wait(lock, [&] { return gate_started; });
    }

    const auto record = [&](int value) {
        std::scoped_lock lock{mutex};
        execution_order.push_back(value);
    };
    worker.QueueWork([&] { record(1); }, Common::ThreadWorkerPriority::Background);
    worker.QueueWork([&] { record(2); }, Common::ThreadWorkerPriority::Normal);
    worker.QueueWork([&] { record(3); }, Common::ThreadWorkerPriority::Foreground);

    const auto snapshot = worker.GetQueueSnapshot();
    REQUIRE(snapshot.pending[static_cast<size_t>(Common::ThreadWorkerPriority::Foreground)] == 1);
    REQUIRE(snapshot.pending[static_cast<size_t>(Common::ThreadWorkerPriority::Normal)] == 1);
    REQUIRE(snapshot.pending[static_cast<size_t>(Common::ThreadWorkerPriority::Background)] == 1);

    {
        std::scoped_lock lock{mutex};
        gate_open = true;
    }
    condition.notify_one();
    worker.WaitForRequests();

    std::scoped_lock lock{mutex};
    REQUIRE(execution_order == std::vector<int>{3, 2, 1});
}
