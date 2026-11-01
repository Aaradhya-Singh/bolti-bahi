"use client";

import { useState, useEffect, useCallback } from "react";
import {
  TrendingUp,
  TrendingDown,
  CreditCard,
  AlertTriangle,
  IndianRupee,
} from "lucide-react";
import { getDashboard } from "@/lib/api";

function formatRupee(amount) {
  if (amount == null) return "₹0";
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}

export default function Dashboard({ shopId, refreshKey }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    if (!shopId) return;
    try {
      setLoading(true);
      const dashboard = await getDashboard(shopId);
      setData(dashboard);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [shopId]);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshKey]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="bg-white rounded-2xl p-4 h-24 animate-pulse"
          >
            <div className="h-3 bg-gray-200 rounded w-16 mb-3" />
            <div className="h-5 bg-gray-200 rounded w-20" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 rounded-2xl p-4 text-center">
        <p className="text-sm text-red-500">डेटा लोड नहीं हुआ</p>
        <button
          onClick={fetchData}
          className="mt-2 text-sm text-red-400 underline min-h-[44px]"
        >
          फिर से कोशिश करें
        </button>
      </div>
    );
  }

  if (!data) return null;

  const cards = [
    {
      label: "आज की बिक्री",
      labelEn: "Sales",
      value: formatRupee(data.today_sales),
      icon: TrendingUp,
      bg: "bg-green-50",
      iconColor: "text-green-500",
      valueColor: "text-green-700",
    },
    {
      label: "आज का खर्च",
      labelEn: "Expenses",
      value: formatRupee(data.today_expenses),
      icon: TrendingDown,
      bg: "bg-red-50",
      iconColor: "text-red-500",
      valueColor: "text-red-700",
    },
    {
      label: "बाकी उधार",
      labelEn: "Credit",
      value: formatRupee(data.outstanding_credit),
      extra: data.credit_customers_count
        ? `${data.credit_customers_count} ग्राहक`
        : null,
      icon: CreditCard,
      bg: "bg-orange-50",
      iconColor: "text-orange-500",
      valueColor: "text-orange-700",
    },
    {
      label: "कम स्टॉक",
      labelEn: "Low Stock",
      value: data.low_stock_count != null ? `${data.low_stock_count} सामान` : "0",
      icon: AlertTriangle,
      bg: "bg-amber-50",
      iconColor: "text-amber-500",
      valueColor: "text-amber-700",
    },
  ];

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className={`${card.bg} rounded-2xl p-4 flex flex-col gap-2`}
            >
              <div className="flex items-center gap-1.5">
                <Icon size={16} className={card.iconColor} />
                <span className="text-xs font-medium text-gray-500">
                  {card.label}
                </span>
              </div>
              <p className={`text-xl font-bold ${card.valueColor}`}>
                {card.value}
              </p>
              {card.extra && (
                <p className="text-xs text-gray-400">{card.extra}</p>
              )}
            </div>
          );
        })}
      </div>

      {/* Estimated Profit */}
      {data.estimated_profit != null && (
        <div className="bg-gradient-to-r from-green-500 to-emerald-600 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-green-100 font-medium">अनुमानित मुनाफ़ा</p>
            <p className="text-2xl font-bold text-white mt-1">
              {formatRupee(data.estimated_profit)}
            </p>
          </div>
          <IndianRupee size={32} className="text-green-200 opacity-60" />
        </div>
      )}
    </div>
  );
}
